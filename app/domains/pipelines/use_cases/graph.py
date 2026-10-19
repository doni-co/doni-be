"""새로고침 후 캔버스를 복원하기 위한 조회: 노드/선 전체 + 노드별 최신 실행 상태를 한 번에 내려준다."""
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.pipelines.schemas import EdgeOut, GraphOut, NodeOut, NodeRunOut
from app.models.pipeline import NodeRun, PipelineEdge, PipelineNode


async def get_pipeline_graph(session: AsyncSession, pipeline_id: int) -> GraphOut:
    db_nodes = (
        await session.execute(select(PipelineNode).where(PipelineNode.pipeline_id == pipeline_id))
    ).scalars().all()
    db_edges = (
        await session.execute(select(PipelineEdge).where(PipelineEdge.pipeline_id == pipeline_id))
    ).scalars().all()

    node_ids = [n.id for n in db_nodes]
    latest_runs: Sequence[NodeRun] = []
    if node_ids:
        latest_runs = (
            await session.execute(
                select(NodeRun)
                .where(NodeRun.node_id.in_(node_ids))
                .order_by(NodeRun.node_id, NodeRun.id.desc())
                .distinct(NodeRun.node_id)  # Postgres: SELECT DISTINCT ON (node_id) ...
            )
        ).scalars().all()

    return GraphOut(
        nodes=[NodeOut.model_validate(n) for n in db_nodes],
        edges=[EdgeOut.model_validate(e) for e in db_edges],
        runs={r.node_id: NodeRunOut.model_validate(r) for r in latest_runs},
    )
