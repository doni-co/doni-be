"""실패한 노드를 재시도한다. params는 바꾸지 않고(이번 범위 밖) 같은 kind로 새 NodeRun을 만들어
다시 큐에 넣는다 — 노드 자체는 새로 만들지 않으므로 캔버스의 위치/연결이 그대로 유지된다."""
from collections.abc import Callable

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.pipelines.errors import Conflict, NodeNotFound
from app.models.enums import NodeRunStatus
from app.models.pipeline import NodeRun, PipelineEdge, PipelineNode

Enqueue = Callable[[int], None]


async def retry_node(
    session: AsyncSession, *, node_id: int, owner_id: int, enqueue: Enqueue
) -> dict:
    node = await session.get(PipelineNode, node_id)
    if node is None:
        raise NodeNotFound(f"node {node_id} not found")

    latest = (
        await session.execute(
            select(NodeRun).where(NodeRun.node_id == node_id).order_by(NodeRun.id.desc())
        )
    ).scalars().first()
    if latest is None or latest.status != NodeRunStatus.FAILED:
        raise Conflict(f"node {node_id} is not in a FAILED state")

    run = NodeRun(node_id=node_id, status=NodeRunStatus.PENDING, attempts=latest.attempts + 1)
    session.add(run)
    try:
        await session.commit()
    except IntegrityError:
        # 부분 유니크 인덱스(ix_node_runs_one_active_per_node) 위반: 이미 진행 중인 실행이 있음(동시 retry 더블클릭).
        await session.rollback()
        raise Conflict(f"node {node_id} already has an active run") from None
    await session.refresh(run)

    try:
        enqueue(run.id)
    except Exception as e:  # noqa: BLE001 - create_step과 동일한 정책: 큐 등록 실패는 그 실행만 즉시 FAILED
        await session.execute(
            update(NodeRun)
            .where(NodeRun.id == run.id, NodeRun.status == NodeRunStatus.PENDING)
            .values(status=NodeRunStatus.FAILED, error=f"큐 등록 실패: {e}")
        )
        await session.commit()
        await session.refresh(run)

    edges = (
        await session.execute(select(PipelineEdge).where(PipelineEdge.dst_node_id == node_id))
    ).scalars().all()
    return {"node": node, "edges": edges, "run": run}
