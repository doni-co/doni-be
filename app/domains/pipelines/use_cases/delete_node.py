"""뒤에 이어진 노드가 없고 진행 중(PENDING/RUNNING)이 아닌 노드만 지운다.
이 노드가 만든 Asset은 보존하고(assets.service.clear_produced_by_node), produced_by_node_id만 비운다."""
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.assets.service import clear_produced_by_node
from app.domains.pipelines.errors import Conflict, NodeNotFound
from app.models.enums import NodeRunStatus
from app.models.pipeline import NodeRun, PipelineEdge, PipelineNode

_IN_PROGRESS = {NodeRunStatus.PENDING, NodeRunStatus.RUNNING}


async def delete_node(session: AsyncSession, node_id: int) -> None:
    node = await session.get(PipelineNode, node_id)
    if node is None:
        raise NodeNotFound(f"node {node_id} not found")

    child_edge = (
        await session.execute(select(PipelineEdge.id).where(PipelineEdge.src_node_id == node_id))
    ).scalars().first()
    if child_edge is not None:
        raise Conflict(f"node {node_id} has downstream nodes; delete them first")

    latest = (
        await session.execute(
            select(NodeRun).where(NodeRun.node_id == node_id).order_by(NodeRun.id.desc())
        )
    ).scalars().first()
    if latest is not None and latest.status in _IN_PROGRESS:
        raise Conflict(f"node {node_id} has an in-progress run")

    await session.execute(delete(PipelineEdge).where(PipelineEdge.dst_node_id == node_id))
    await session.execute(delete(NodeRun).where(NodeRun.node_id == node_id))
    await clear_produced_by_node(session, node_id)  # 자체 commit (assets/service.py 관례)

    await session.delete(node)
    await session.commit()
