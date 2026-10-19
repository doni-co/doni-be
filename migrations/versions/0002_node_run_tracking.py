"""node_runs에 시간 추적 컬럼 추가 + 노드당 진행 중(PENDING/RUNNING) 실행 1개 제한

PENDING 판단(created_at), RUNNING 소요시간/멈춤 판단(started_at), 종료 시각(finished_at)에 쓴다.
부분 유니크 인덱스는 같은 노드에 동시에 두 개의 PENDING/RUNNING NodeRun이 생기는 걸 DB 레벨에서 막는다
(retry 더블클릭 등으로 인한 중복 실행 방지).

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-18
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "node_runs",
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.add_column("node_runs", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("node_runs", sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True))

    op.create_index(
        "ix_node_runs_one_active_per_node",
        "node_runs",
        ["node_id"],
        unique=True,
        # sa.Enum(NodeRunStatus)는 기본적으로 멤버 "이름"을 저장한다(.value인 "pending"이 아니라
        # "PENDING") - 아래 두 값은 NodeRunStatus.PENDING.name / NodeRunStatus.RUNNING.name과 같아야 한다.
        postgresql_where=sa.text("status IN ('PENDING', 'RUNNING')"),
    )


def downgrade() -> None:
    op.drop_index("ix_node_runs_one_active_per_node", table_name="node_runs")
    op.drop_column("node_runs", "finished_at")
    op.drop_column("node_runs", "started_at")
    op.drop_column("node_runs", "created_at")
