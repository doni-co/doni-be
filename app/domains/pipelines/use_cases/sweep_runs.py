"""멈춘 실행 정리. Celery beat 등 스케줄러에 걸지 않고, 필요할 때 수동/관리자 호출로만 쓴다
(정기 실행은 다음 단계로 미룸 — 범위는 README/설계 메모 참고).
재등록은 하지 않는다: 오래된 PENDING/RUNNING을 FAILED로 마감만 하고, 사용자가 retry하게 한다."""
from datetime import timedelta

from sqlalchemy import func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import NodeRunStatus
from app.models.pipeline import NodeRun


async def sweep_stuck_runs(
    session: AsyncSession, *, running_after_minutes: int = 15, pending_after_minutes: int = 30
) -> int:
    running_cutoff = func.now() - timedelta(minutes=running_after_minutes)
    pending_cutoff = func.now() - timedelta(minutes=pending_after_minutes)

    running_result = await session.execute(
        update(NodeRun)
        .where(NodeRun.status == NodeRunStatus.RUNNING, NodeRun.started_at < running_cutoff)
        .values(status=NodeRunStatus.FAILED, error="워커 중단 또는 시간 초과", finished_at=func.now())
    )
    pending_result = await session.execute(
        update(NodeRun)
        .where(NodeRun.status == NodeRunStatus.PENDING, NodeRun.created_at < pending_cutoff)
        .values(status=NodeRunStatus.FAILED, error="큐 등록 실패 또는 지연, 재시도하세요", finished_at=func.now())
    )
    await session.commit()
    return running_result.rowcount + pending_result.rowcount
