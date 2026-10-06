from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.domains.pipelines import service
from app.domains.pipelines.schemas import EdgeCreate, NodeCreate, PipelineCreate, RunOut

router = APIRouter(prefix="/pipelines", tags=["pipelines"])


@router.post("")
async def create_route(body: PipelineCreate, owner_id: int = 1, session: AsyncSession = Depends(get_session)):
    pipeline = await service.create_pipeline(session, owner_id, body.name)
    return {"id": pipeline.id, "name": pipeline.name}


@router.post("/{pipeline_id}/nodes")
async def add_node_route(pipeline_id: int, body: NodeCreate, session: AsyncSession = Depends(get_session)):
    node = await service.add_node(session, pipeline_id, body.kind, body.params, body.position)
    return {"id": node.id, "kind": node.kind}


@router.post("/{pipeline_id}/edges")
async def add_edge_route(pipeline_id: int, body: EdgeCreate, session: AsyncSession = Depends(get_session)):
    edge = await service.add_edge(session, pipeline_id, body.src_node_id, body.dst_node_id, body.dst_port)
    return {"id": edge.id}


@router.post("/{pipeline_id}/runs", response_model=RunOut)
async def start_run_route(pipeline_id: int, session: AsyncSession = Depends(get_session)):
    return await service.start_run(session, pipeline_id)
