from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.domains.pipelines.rules.graph_rules import validate_new_edge
from app.domains.pipelines.schemas import EdgeCreate, NodeCreate, NodeRunOut, PipelineCreate
from app.domains.pipelines.tasks import execute_node_task
from app.models.pipeline import NodeRun, Pipeline, PipelineEdge, PipelineNode

router = APIRouter(prefix="/pipelines", tags=["pipelines"])


@router.post("")
async def create_pipeline_route(body: PipelineCreate, owner_id: int = 1, session: AsyncSession = Depends(get_session)):
    pipeline = Pipeline(owner_id=owner_id, name=body.name)
    session.add(pipeline)
    await session.commit()
    await session.refresh(pipeline)
    return {"id": pipeline.id, "name": pipeline.name}


@router.post("/{pipeline_id}/nodes")
async def add_node_route(pipeline_id: int, body: NodeCreate, session: AsyncSession = Depends(get_session)):
    node = PipelineNode(
        pipeline_id=pipeline_id, kind=body.kind, params=body.params,
        position=body.position, source_asset_id=body.source_asset_id,
    )
    session.add(node)
    await session.commit()
    await session.refresh(node)
    return {"id": node.id, "kind": node.kind}


@router.post("/{pipeline_id}/edges")
async def add_edge_route(pipeline_id: int, body: EdgeCreate, session: AsyncSession = Depends(get_session)):
    existing = (
        await session.execute(select(PipelineEdge).where(PipelineEdge.pipeline_id == pipeline_id))
    ).scalars().all()
    node_ids = (
        await session.execute(select(PipelineNode.id).where(PipelineNode.pipeline_id == pipeline_id))
    ).scalars().all()

    validate_new_edge(
        set(node_ids),
        [(e.src_node_id, e.dst_node_id) for e in existing],
        (body.src_node_id, body.dst_node_id),
    )

    edge = PipelineEdge(
        pipeline_id=pipeline_id, src_node_id=body.src_node_id,
        dst_node_id=body.dst_node_id, dst_port=body.dst_port,
    )
    session.add(edge)
    await session.commit()
    await session.refresh(edge)
    return {"id": edge.id}


@router.post("/nodes/{node_id}/execute", response_model=NodeRunOut)
async def execute_node_route(node_id: int, owner_id: int = 1):
    """화면에서 노드를 클릭해 transform 실행을 누르면 호출되는 엔드포인트.
    실제 계산은 큐에 넣고(worker가 처리) 즉시 PENDING 상태의 NodeRun을 돌려준다.
    프런트는 이 NodeRun.id로 상태를 폴링해서 완료 여부와 결과(output_ref)를 확인한다."""
    # NodeRun을 미리 만들지 않고 바로 큐에 넣는다 - 실제 PENDING/RUNNING 생성은 execute_node()가 담당.
    execute_node_task.delay(node_id, owner_id)
    return {"id": 0, "node_id": node_id, "status": "pending", "output_kind": None, "output_ref": None, "error": None}


@router.get("/nodes/{node_id}/runs/latest", response_model=NodeRunOut)
async def get_latest_node_run_route(node_id: int, session: AsyncSession = Depends(get_session)):
    """프런트가 실행 상태를 폴링하는 엔드포인트."""
    run = (
        await session.execute(
            select(NodeRun).where(NodeRun.node_id == node_id).order_by(NodeRun.id.desc())
        )
    ).scalars().first()
    return run
