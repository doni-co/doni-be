"""그래프 검증, 상태 전이, Run 오케스트레이션을 한곳에 둔다.
(순수 로직을 별도 레이어로 격리하지 않음 - 2인/3개월 속도를 위한 의도적 단순화.
 다만 media/datasets 테이블은 직접 쿼리하지 않고 반드시 그쪽 service 함수를 호출한다.)"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import NodeRunStatus, RunStatus
from app.models.pipeline import NodeRun, Pipeline, PipelineEdge, PipelineNode, PipelineRun

_ALLOWED_TRANSITIONS = {
    RunStatus.PENDING: {RunStatus.RUNNING, RunStatus.CANCELED},
    RunStatus.RUNNING: {RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELED},
}
_ALLOWED_NODE_TRANSITIONS = {
    NodeRunStatus.PENDING: {NodeRunStatus.RUNNING, NodeRunStatus.SKIPPED},
    NodeRunStatus.RUNNING: {NodeRunStatus.SUCCEEDED, NodeRunStatus.FAILED},
}


class InvalidStateTransition(Exception):
    pass


class PipelineValidationError(Exception):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(", ".join(errors))


async def create_pipeline(session: AsyncSession, owner_id: int, name: str) -> Pipeline:
    pipeline = Pipeline(owner_id=owner_id, name=name)
    session.add(pipeline)
    await session.commit()
    await session.refresh(pipeline)
    return pipeline


async def add_node(session: AsyncSession, pipeline_id: int, kind: str, params: dict, position: dict) -> PipelineNode:
    node = PipelineNode(pipeline_id=pipeline_id, kind=kind, params=params, position=position)
    session.add(node)
    await session.commit()
    await session.refresh(node)
    return node


def _has_cycle(node_ids: set[int], edges: list[tuple[int, int]]) -> bool:
    graph: dict[int, list[int]] = {n: [] for n in node_ids}
    for src, dst in edges:
        graph.setdefault(src, []).append(dst)
    visiting, visited = set(), set()

    def dfs(n: int) -> bool:
        if n in visiting:
            return True
        if n in visited:
            return False
        visiting.add(n)
        for nxt in graph.get(n, []):
            if dfs(nxt):
                return True
        visiting.discard(n)
        visited.add(n)
        return False

    return any(dfs(n) for n in node_ids)


async def add_edge(session: AsyncSession, pipeline_id: int, src_node_id: int, dst_node_id: int, dst_port: str = "default") -> PipelineEdge:
    existing = (
        await session.execute(select(PipelineEdge).where(PipelineEdge.pipeline_id == pipeline_id))
    ).scalars().all()
    nodes = (
        await session.execute(select(PipelineNode.id).where(PipelineNode.pipeline_id == pipeline_id))
    ).scalars().all()

    edges = [(e.src_node_id, e.dst_node_id) for e in existing] + [(src_node_id, dst_node_id)]
    if _has_cycle(set(nodes), edges):
        raise PipelineValidationError(["edge would create a cycle"])
    # TODO: 노드 kind의 input_kinds/output_kind를 transforms.registry에서 조회해 입출력 타입도 검증

    edge = PipelineEdge(pipeline_id=pipeline_id, src_node_id=src_node_id, dst_node_id=dst_node_id, dst_port=dst_port)
    session.add(edge)
    await session.commit()
    await session.refresh(edge)
    return edge


async def start_run(session: AsyncSession, pipeline_id: int) -> PipelineRun:
    nodes = (
        await session.execute(select(PipelineNode).where(PipelineNode.pipeline_id == pipeline_id))
    ).scalars().all()

    run = PipelineRun(pipeline_id=pipeline_id, status=RunStatus.PENDING)
    session.add(run)
    await session.flush()

    for node in nodes:
        session.add(NodeRun(run_id=run.id, node_id=node.id, status=NodeRunStatus.PENDING))

    await session.commit()
    await session.refresh(run)

    from app.domains.pipelines.tasks import execute_run  # 순환 import 방지용 지연 import
    execute_run.delay(run.id)
    return run


async def mark_run(session: AsyncSession, run_id: int, new_status: RunStatus, **fields) -> PipelineRun:
    run = await session.get(PipelineRun, run_id)
    if new_status not in _ALLOWED_TRANSITIONS.get(run.status, set()):
        raise InvalidStateTransition(f"{run.status} -> {new_status}")
    run.status = new_status
    for k, v in fields.items():
        setattr(run, k, v)
    await session.commit()
    return run


async def mark_node_run(session: AsyncSession, node_run_id: int, new_status: NodeRunStatus, **fields) -> NodeRun:
    node_run = await session.get(NodeRun, node_run_id)
    if new_status not in _ALLOWED_NODE_TRANSITIONS.get(node_run.status, set()):
        raise InvalidStateTransition(f"{node_run.status} -> {new_status}")
    node_run.status = new_status
    for k, v in fields.items():
        setattr(node_run, k, v)
    await session.commit()
    return node_run
