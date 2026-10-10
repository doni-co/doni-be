"""Celery 작업. api 프로세스가 큐에 넣은 "node_id"만 받아서 worker 프로세스가 실제로 실행한다.
작은 id만 주고받으므로, 나중에 원격 워커로 바뀌어도 이 계약은 그대로 유지된다."""
import asyncio

from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.domains.pipelines.use_cases.execute_node import execute_node


@celery_app.task(name="app.domains.pipelines.tasks.execute_node_task")
def execute_node_task(node_id: int, owner_id: int) -> None:
    asyncio.run(_execute_node_async(node_id, owner_id))


async def _execute_node_async(node_id: int, owner_id: int) -> None:
    async with SessionLocal() as session:
        await execute_node(session, node_id, owner_id)
