"""assets에 업로드 메타데이터 컬럼 추가, uploadstatus에 INVALID 추가

feat/data-connection이 Asset에 size_bytes/content_type/sha256/created_at을 추가하고
UploadStatus에 INVALID를 추가했는데, migrations/는 그보다 먼저(0001) 만들어져서 반영이
안 돼 있었다. 모델(app/models/asset.py, app/models/enums.py)과 실제 DB 스키마를 맞춘다.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-19
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("assets", sa.Column("size_bytes", sa.Integer(), nullable=True))
    op.add_column("assets", sa.Column("content_type", sa.String(255), nullable=True))
    op.add_column("assets", sa.Column("sha256", sa.String(64), nullable=True))
    op.add_column(
        "assets",
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    # IF NOT EXISTS: 0001을 이 merge 이후(=모델에 이미 INVALID가 있는 상태)에 처음 돌린 DB에서는
    # uploadstatus 타입이 생성 시점에 이미 INVALID를 포함하므로, 멱등하게 처리해 둘 다 안전하게 한다.
    op.execute("ALTER TYPE uploadstatus ADD VALUE IF NOT EXISTS 'INVALID'")


def downgrade() -> None:
    op.drop_column("assets", "created_at")
    op.drop_column("assets", "sha256")
    op.drop_column("assets", "content_type")
    op.drop_column("assets", "size_bytes")
    # Postgres는 enum 라벨을 제거하는 ALTER TYPE ... DROP VALUE를 지원하지 않아 uploadstatus는 되돌리지 않는다.
