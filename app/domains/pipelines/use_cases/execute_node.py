"""NodeRun 하나를 실제로 실행하는 유스케이스(워커가 호출). create_step/retry_node가 이미
PENDING NodeRun을 만들어 둔 상태에서 run_id만 받아 처리한다 (NodeRun 생성은 이 함수의 책임이 아님).

흐름: 조건부 UPDATE로 선점(PENDING -> RUNNING) -> 입력 Asset 결정(Edge 기반) -> 입력 로드
      -> Transform 실행 -> 결과를 새 Asset으로 저장 -> 조건부 UPDATE(RUNNING -> SUCCEEDED/FAILED).
모든 상태 변경은 "현재 상태가 X일 때만" 조건이 달린 UPDATE라서, 같은 작업이 중복 전달되거나
청소 작업과 경합해도 둘 이상이 동시에 통과하지 않는다(0행이면 조용히 종료).
"""
import inspect

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.assets.service import get_asset, get_rows, register_asset, save_rows
from app.domains.pipelines import nodes  # noqa: F401  (import 시 전체 노드가 registry에 등록됨)
from app.domains.pipelines.nodes.base import TransformResult
from app.domains.pipelines.nodes.registry import get as get_transform
from app.models.enums import AssetKind, AssetOrigin, NodeRunStatus
from app.models.pipeline import NodeRun, PipelineEdge, PipelineNode


async def _resolve_input_asset_ids(session: AsyncSession, node: PipelineNode) -> list[int]:
    """이 노드로 들어오는 Edge를 보고 입력 Asset id들을 구한다.
    업로드 직후의 source 노드는 Edge 없이 자기 자신의 source_asset_id가 입력이다."""
    if node.kind == "source":
        if node.source_asset_id is None:
            raise ValueError("source node has no asset attached")
        return [node.source_asset_id]

    edges = (
        await session.execute(
            select(PipelineEdge).where(PipelineEdge.dst_node_id == node.id).order_by(PipelineEdge.id)
        )
    ).scalars().all()
    if not edges:
        raise ValueError("node has no input connected")

    input_asset_ids = []
    for edge in edges:
        src_node = await session.get(PipelineNode, edge.src_node_id)
        src_run = (
            await session.execute(
                select(NodeRun)
                .where(NodeRun.node_id == src_node.id, NodeRun.status == NodeRunStatus.SUCCEEDED)
                .order_by(NodeRun.id.desc())
            )
        ).scalars().first()
        if src_node.kind == "source":
            input_asset_ids.append(src_node.source_asset_id)
        elif src_run is not None:
            input_asset_ids.append(src_run.output_ref)
        else:
            raise ValueError(f"upstream node {src_node.id} has not produced output yet")
    return input_asset_ids


async def execute_node(session: AsyncSession, run_id: int, owner_id: int) -> NodeRun | None:
    claim = await session.execute(
        update(NodeRun)
        .where(NodeRun.id == run_id, NodeRun.status == NodeRunStatus.PENDING)
        .values(status=NodeRunStatus.RUNNING, started_at=func.now())
    )
    await session.commit()
    if claim.rowcount == 0:
        # 다른 워커가 이미 집어갔거나, 청소 작업이 먼저 FAILED로 마감했거나, 중복 전달된 메시지.
        return None

    node_run = await session.get(NodeRun, run_id)
    assert node_run is not None  # 방금 이 id로 claim에 성공했으므로 항상 존재한다
    node = await session.get(PipelineNode, node_run.node_id)

    try:
        if node is None:
            raise ValueError(f"node {node_run.node_id} not found")

        input_asset_ids = await _resolve_input_asset_ids(session, node)
        transform_cls = get_transform(node.kind)
        params = transform_cls.Params(**node.params)

        # mediaset(비정형) 입력: PDF/이미지 추출처럼 run_media()를 쓰는 노드
        if hasattr(transform_cls, "run_media"):
            asset = await get_asset(session, input_asset_ids[0])
            result: TransformResult = await transform_cls().run_media(asset.storage_key, params)
        else:
            inputs = [await get_rows(session, aid) for aid in input_asset_ids]
            maybe_coro = transform_cls().run(inputs, params)
            result = await maybe_coro if inspect.isawaitable(maybe_coro) else maybe_coro

        new_asset = await register_asset(
            session, owner_id=owner_id, name=f"{node.kind} 결과", kind=AssetKind.DATASET,
            origin=AssetOrigin.NODE_OUTPUT, source_asset_id=input_asset_ids[0],
            produced_by_node_id=node.id,
        )
        await save_rows(session, new_asset.id, result.columns, result.rows)

        await session.execute(
            update(NodeRun)
            .where(NodeRun.id == run_id, NodeRun.status == NodeRunStatus.RUNNING)
            .values(
                status=NodeRunStatus.SUCCEEDED, output_kind=AssetKind.DATASET.value,
                output_ref=new_asset.id, finished_at=func.now(),
            )
        )
        await session.commit()

    except Exception as e:  # noqa: BLE001 - 어떤 예외든 NodeRun.error로 남기고 FAILED 처리
        # DB 제약 위반 등으로 실패했다면 세션이 "rollback 전엔 아무 쿼리도 못 받는" 상태일 수 있다.
        # 그 상태에서 바로 FAILED UPDATE를 실행하면 PendingRollbackError가 나서 실패 기록 자체가 묻힌다.
        await session.rollback()
        await session.execute(
            update(NodeRun)
            .where(NodeRun.id == run_id, NodeRun.status == NodeRunStatus.RUNNING)
            .values(status=NodeRunStatus.FAILED, error=str(e), finished_at=func.now())
        )
        await session.commit()

    await session.refresh(node_run)
    return node_run
