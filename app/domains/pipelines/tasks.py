"""Celery 작업. api 프로세스가 큐에 넣은 "run_id"(NodeRun.id)만 받아서 worker 프로세스가 실제로 실행한다.
NodeRun은 api 프로세스가 미리 PENDING으로 만들어 commit해 둔 뒤 이 run_id를 넘긴다(create_step/retry_node).
작은 id만 주고받으므로, 나중에 원격 워커로 바뀌어도 이 계약은 그대로 유지된다."""
import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.celery_app import celery_app
from app.core.config import settings
from app.domains.pipelines.use_cases.execute_node import execute_node


@celery_app.task(name="app.domains.pipelines.tasks.execute_node_task")
def execute_node_task(run_id: int, owner_id: int) -> None:
    asyncio.run(_execute_node_async(run_id, owner_id))


async def _execute_node_async(run_id: int, owner_id: int) -> None:
    # 워커는 작업마다 asyncio.run()으로 새 이벤트 루프를 연다. api 프로세스용 풀링된 전역 엔진
    # (app.db.session.SessionLocal)을 그대로 쓰면, 두 번째 작업부터 "이전(이미 닫힌) 이벤트 루프에
    # 묶인 커넥션"을 풀에서 꺼내 쓰려다 깨진다(asyncpg 커넥션은 이벤트 루프 경계를 못 넘음).
    # 그래서 작업마다 NullPool로 새 엔진을 만들고 끝나면 버린다 - 재사용할 커넥션이 없으니 이 문제가 없다.
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            await execute_node(session, run_id, owner_id)
    finally:
        await engine.dispose()
