"""Celery 작업. API 프로세스와 분리되어 워커에서 실행된다.
워커는 run_id만 받아 DB에서 조회하므로, 나중에 원격 워커로 바뀌어도 이 계약은 그대로 유지된다."""
import asyncio

from sqlalchemy import select

from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.domains.pipelines import service
from app.domains.pipelines.transforms import registry
from app.domains.pipelines.transforms.base import TransformContext
from app.models.enums import NodeRunStatus, RunStatus
from app.models.pipeline import NodeRun, PipelineNode


@celery_app.task(name="app.domains.pipelines.tasks.execute_run")
def execute_run(run_id: int) -> None:
    asyncio.run(_execute_run_async(run_id))


async def _execute_run_async(run_id: int) -> None:
    async with SessionLocal() as session:
        await service.mark_run(session, run_id, RunStatus.RUNNING)

        node_runs = (
            await session.execute(select(NodeRun).where(NodeRun.run_id == run_id))
        ).scalars().all()

        failed = False
        for node_run in node_runs:
            await service.mark_node_run(session, node_run.id, NodeRunStatus.RUNNING)
            try:
                node = await session.get(PipelineNode, node_run.node_id)
                transform_cls = registry.get(node.kind)
                result = await transform_cls().run([], transform_cls.Params(**node.params), TransformContext(session=session))
                await service.mark_node_run(
                    session, node_run.id, NodeRunStatus.SUCCEEDED,
                    output_kind=result.output_kind, output_ref=result.output_ref,
                )
            except Exception as e:  # noqa: BLE001
                failed = True
                await service.mark_node_run(session, node_run.id, NodeRunStatus.FAILED, error=str(e))

        await service.mark_run(session, run_id, RunStatus.FAILED if failed else RunStatus.SUCCEEDED)
