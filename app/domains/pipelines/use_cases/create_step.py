"""통합 엔드포인트(POST /pipelines/nodes/transform|join|union)의 공통 로직.
노드 + 선 + 실행 기록(PENDING)을 한 트랜잭션으로 저장/commit한 뒤 그 run_id를 큐에 등록한다.
큐 등록이 실패해도 노드/선/실행 기록은 이미 commit되어 있으므로 노드는 보존되고,
그 실행만 조건부 UPDATE로 즉시 FAILED로 남는다(거짓 "대기 중" 상태를 보여주지 않기 위함)."""
from collections.abc import Callable

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.pipelines import nodes  # noqa: F401  (import 시 전체 노드가 registry에 등록됨)
from app.domains.pipelines.errors import Conflict, InvalidRequest, NodeNotFound
from app.domains.pipelines.nodes.registry import get as get_transform
from app.models.enums import NodeRunStatus
from app.models.pipeline import NodeRun, PipelineEdge, PipelineNode

Enqueue = Callable[[int], None]


async def _assert_input_ready(session: AsyncSession, node: PipelineNode) -> None:
    """입력 노드가 이미 결과를 내놓은 상태인지 확인한다(source는 즉시 준비,
    그 외는 최신 실행이 SUCCEEDED여야 함). 기존 execute_node._resolve_input_asset_ids의 판단과 동일한 기준."""
    if node.kind == "source":
        if node.source_asset_id is None:
            raise Conflict(f"node {node.id} has no asset attached")
        return
    latest = (
        await session.execute(
            select(NodeRun).where(NodeRun.node_id == node.id).order_by(NodeRun.id.desc())
        )
    ).scalars().first()
    if latest is None or latest.status != NodeRunStatus.SUCCEEDED:
        raise Conflict(f"node {node.id} has no successful output yet")


async def _create_step(
    session: AsyncSession,
    *,
    kind: str,
    input_node_ids: list[int],
    dst_ports: list[str],
    params: dict,
    position: dict,
    owner_id: int,
    enqueue: Enqueue,
) -> dict:
    try:
        transform_cls = get_transform(kind)
    except ValueError as e:
        raise InvalidRequest(str(e)) from None

    if transform_cls.input_count != len(input_node_ids):
        raise InvalidRequest(
            f"{kind} expects {transform_cls.input_count} input(s), got {len(input_node_ids)}"
        )

    try:
        validated_params = transform_cls.Params(**params)
    except Exception as e:  # noqa: BLE001 - pydantic ValidationError 등을 422로 변환
        raise InvalidRequest(str(e)) from None

    input_nodes = (
        await session.execute(select(PipelineNode).where(PipelineNode.id.in_(input_node_ids)))
    ).scalars().all()
    found = {n.id: n for n in input_nodes}
    missing = [i for i in input_node_ids if i not in found]
    if missing:
        raise NodeNotFound(f"node(s) not found: {missing}")

    pipeline_ids = {n.pipeline_id for n in found.values()}
    if len(pipeline_ids) != 1:
        raise InvalidRequest("input nodes belong to different pipelines")
    pipeline_id = pipeline_ids.pop()

    for node_id in input_node_ids:
        await _assert_input_ready(session, found[node_id])

    node = PipelineNode(
        pipeline_id=pipeline_id, kind=kind,
        params=validated_params.model_dump(), position=position,
    )
    session.add(node)
    await session.flush()  # node.id 확보 (아직 commit은 안 함)

    edges = [
        PipelineEdge(pipeline_id=pipeline_id, src_node_id=src_id, dst_node_id=node.id, dst_port=port)
        for src_id, port in zip(input_node_ids, dst_ports, strict=True)
    ]
    session.add_all(edges)

    run = NodeRun(node_id=node.id, status=NodeRunStatus.PENDING, attempts=1)
    session.add(run)

    await session.commit()
    await session.refresh(node)
    for edge in edges:
        await session.refresh(edge)
    await session.refresh(run)

    try:
        enqueue(run.id)
    except Exception as e:  # noqa: BLE001 - 큐 등록 실패는 노드를 지우지 않고 그 실행만 FAILED로 남긴다
        await session.execute(
            update(NodeRun)
            .where(NodeRun.id == run.id, NodeRun.status == NodeRunStatus.PENDING)
            .values(status=NodeRunStatus.FAILED, error=f"큐 등록 실패: {e}")
        )
        await session.commit()
        await session.refresh(run)

    return {"node": node, "edges": edges, "run": run}


async def create_transform_step(
    session: AsyncSession, *, input_node_id: int, kind: str, params: dict, position: dict,
    owner_id: int, enqueue: Enqueue,
) -> dict:
    try:
        transform_cls = get_transform(kind)
    except ValueError as e:
        raise InvalidRequest(str(e)) from None
    if transform_cls.input_count != 1:
        raise InvalidRequest(
            f"{kind}은 입력이 여러 개인 노드입니다. /pipelines/nodes/join 또는 /pipelines/nodes/union을 사용하세요"
        )
    return await _create_step(
        session, kind=kind, input_node_ids=[input_node_id], dst_ports=["input"],
        params=params, position=position, owner_id=owner_id, enqueue=enqueue,
    )


async def create_join_step(
    session: AsyncSession, *, left_node_id: int, right_node_id: int, params: dict, position: dict,
    owner_id: int, enqueue: Enqueue,
) -> dict:
    return await _create_step(
        session, kind="join", input_node_ids=[left_node_id, right_node_id], dst_ports=["left", "right"],
        params=params, position=position, owner_id=owner_id, enqueue=enqueue,
    )


async def create_union_step(
    session: AsyncSession, *, node_ids: list[int], params: dict, position: dict,
    owner_id: int, enqueue: Enqueue,
) -> dict:
    return await _create_step(
        session, kind="union", input_node_ids=list(node_ids), dst_ports=["a", "b"],
        params=params, position=position, owner_id=owner_id, enqueue=enqueue,
    )
