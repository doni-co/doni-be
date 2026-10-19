from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.domains.pipelines.schemas import (
    GraphOut,
    JoinNodeCreate,
    NodeCreate,
    NodeRunOut,
    NodeWithRunOut,
    PipelineCreate,
    TransformNodeCreate,
    UnionNodeCreate,
)
from app.domains.pipelines.tasks import execute_node_task
from app.domains.pipelines.use_cases.create_step import (
    create_join_step,
    create_transform_step,
    create_union_step,
)
from app.domains.pipelines.use_cases.delete_node import delete_node
from app.domains.pipelines.use_cases.graph import get_pipeline_graph
from app.domains.pipelines.use_cases.retry_node import retry_node
from app.models.pipeline import NodeRun, Pipeline, PipelineNode

router = APIRouter(prefix="/pipelines", tags=["pipelines"])


def _enqueue(run_id: int, owner_id: int) -> None:
    execute_node_task.delay(run_id, owner_id)


@router.post("")
async def create_pipeline_route(body: PipelineCreate, owner_id: int = 1, session: AsyncSession = Depends(get_session)):
    pipeline = Pipeline(owner_id=owner_id, name=body.name)
    session.add(pipeline)
    await session.commit()
    await session.refresh(pipeline)
    return {"id": pipeline.id, "name": pipeline.name}


@router.post("/{pipeline_id}/nodes")
async def add_node_route(pipeline_id: int, body: NodeCreate, session: AsyncSession = Depends(get_session)):
    """source 노드(업로드된 Asset을 캔버스에 올림) 생성 전용. 변환/결합/통합 노드는
    POST /pipelines/nodes/transform|join|union 을 쓴다(노드+선+실행 기록을 한 번에 만듦)."""
    node = PipelineNode(
        pipeline_id=pipeline_id, kind=body.kind, params=body.params,
        position=body.position, source_asset_id=body.source_asset_id,
    )
    session.add(node)
    await session.commit()
    await session.refresh(node)
    return {"id": node.id, "kind": node.kind}


@router.post("/nodes/transform", response_model=NodeWithRunOut, status_code=202)
async def create_transform_route(body: TransformNodeCreate, owner_id: int = 1, session: AsyncSession = Depends(get_session)):
    return await create_transform_step(
        session, input_node_id=body.input_node_id, kind=body.kind, params=body.params,
        position=body.position, owner_id=owner_id,
        enqueue=lambda run_id: _enqueue(run_id, owner_id),
    )


@router.post("/nodes/join", response_model=NodeWithRunOut, status_code=202)
async def create_join_route(body: JoinNodeCreate, owner_id: int = 1, session: AsyncSession = Depends(get_session)):
    return await create_join_step(
        session, left_node_id=body.left_node_id, right_node_id=body.right_node_id,
        params=body.params, position=body.position, owner_id=owner_id,
        enqueue=lambda run_id: _enqueue(run_id, owner_id),
    )


@router.post("/nodes/union", response_model=NodeWithRunOut, status_code=202)
async def create_union_route(body: UnionNodeCreate, owner_id: int = 1, session: AsyncSession = Depends(get_session)):
    return await create_union_step(
        session, node_ids=body.node_ids, params={}, position=body.position, owner_id=owner_id,
        enqueue=lambda run_id: _enqueue(run_id, owner_id),
    )


@router.post("/nodes/{node_id}/retry", response_model=NodeWithRunOut, status_code=202)
async def retry_node_route(node_id: int, owner_id: int = 1, session: AsyncSession = Depends(get_session)):
    return await retry_node(
        session, node_id=node_id, owner_id=owner_id,
        enqueue=lambda run_id: _enqueue(run_id, owner_id),
    )


@router.delete("/nodes/{node_id}", status_code=204)
async def delete_node_route(node_id: int, session: AsyncSession = Depends(get_session)):
    await delete_node(session, node_id)
    return Response(status_code=204)


@router.get("/nodes/{node_id}/runs/latest", response_model=NodeRunOut)
async def get_latest_node_run_route(node_id: int, session: AsyncSession = Depends(get_session)):
    """프런트가 실행 상태를 폴링하는 엔드포인트."""
    run = (
        await session.execute(
            select(NodeRun).where(NodeRun.node_id == node_id).order_by(NodeRun.id.desc())
        )
    ).scalars().first()
    return run


@router.get("/{pipeline_id}/graph", response_model=GraphOut)
async def get_pipeline_graph_route(pipeline_id: int, session: AsyncSession = Depends(get_session)):
    """새로고침 후 캔버스(노드/선/각 노드 최신 실행 상태)를 복원한다."""
    return await get_pipeline_graph(session, pipeline_id)
