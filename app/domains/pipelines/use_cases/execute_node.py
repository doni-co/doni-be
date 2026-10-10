"""노드 하나를 실제로 실행하는 유스케이스. 화면에서 노드를 클릭해 transform을 지정하고
실행했을 때 호출되는 지점이다 (파이프라인 전체를 묶어 실행하는 개념은 없음).

흐름: PipelineNode 조회 -> 입력 Asset 결정(Edge 기반) -> 입력 로드 -> Transform 실행
      -> 결과를 새 Asset으로 저장 -> NodeRun 상태 갱신.
media_set 입력(PDF/이미지 추출)과 dataset 입력(일반 transform)을 분기 처리한다.
"""
import inspect

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.assets.service import get_asset, get_rows, register_asset, save_rows
from app.domains.pipelines.nodes.base import TransformResult
from app.domains.pipelines.nodes.registry import get as get_transform
from app.domains.pipelines.rules.state_rules import assert_transition
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
        await session.execute(select(PipelineEdge).where(PipelineEdge.dst_node_id == node.id))
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


async def execute_node(session: AsyncSession, node_id: int, owner_id: int) -> NodeRun:
    node = await session.get(PipelineNode, node_id)
    if node is None:
        raise ValueError("node not found")

    node_run = NodeRun(node_id=node.id, status=NodeRunStatus.PENDING)
    session.add(node_run)
    await session.commit()
    await session.refresh(node_run)

    assert_transition(node_run.status, NodeRunStatus.RUNNING)
    node_run.status = NodeRunStatus.RUNNING
    await session.commit()

    try:
        input_asset_ids = await _resolve_input_asset_ids(session, node)
        transform_cls = get_transform(node.kind)
        params = transform_cls.Params(**node.params)

        # media_set(비정형) 입력: PDF/이미지 추출처럼 run_media()를 쓰는 노드
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

        assert_transition(node_run.status, NodeRunStatus.SUCCEEDED)
        node_run.status = NodeRunStatus.SUCCEEDED
        node_run.output_kind = AssetKind.DATASET.value
        node_run.output_ref = new_asset.id
        await session.commit()

    except Exception as e:  # noqa: BLE001 - 어떤 예외든 NodeRun.error로 남기고 FAILED 처리
        assert_transition(node_run.status, NodeRunStatus.FAILED)
        node_run.status = NodeRunStatus.FAILED
        node_run.error = str(e)
        await session.commit()

    await session.refresh(node_run)
    return node_run
