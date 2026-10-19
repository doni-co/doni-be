"""initial schema (users, uploads, pipelines, pipeline_nodes, assets, asset_rows, pipeline_edges, node_runs)

처음 생성되는 마이그레이션이라 지금까지 models/*.py에 쌓인 전체 테이블을 빈 DB 기준으로 한 번에 만든다.
assets.produced_by_node_id <-> pipeline_nodes.source_asset_id가 서로를 가리키는 순환 FK라서,
두 테이블을 먼저 FK 없이/일부만 걸어서 만들고 나머지 FK는 생성 후 alter로 붙인다.

Revision ID: 0001
Revises:
Create Date: 2026-10-18
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

from app.models.enums import AssetKind, AssetOrigin, AssetStatus, NodeRunStatus, UploadStatus

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "uploads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("original_filename", sa.String(512), nullable=False),
        sa.Column("storage_key", sa.String(1024), nullable=False),
        sa.Column("status", sa.Enum(UploadStatus, name="uploadstatus"), nullable=False),
        sa.Column("asset_kind", sa.Enum(AssetKind, name="assetkind"), nullable=True),
        sa.Column("asset_id", sa.Integer(), nullable=True),
        sa.Column("error", sa.String(2000), nullable=True),
    )

    op.create_table(
        "pipelines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
    )

    op.create_table(
        "pipeline_nodes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("pipeline_id", sa.Integer(), sa.ForeignKey("pipelines.id"), nullable=False),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("params", JSONB, nullable=False),
        sa.Column("position", JSONB, nullable=False),
        sa.Column("source_asset_id", sa.Integer(), nullable=True),  # FK는 assets 생성 후 아래서 추가
    )

    op.create_table(
        "assets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("kind", sa.Enum(AssetKind, name="assetkind"), nullable=False),
        sa.Column("status", sa.Enum(AssetStatus, name="assetstatus"), nullable=False),
        sa.Column("origin", sa.Enum(AssetOrigin, name="assetorigin"), nullable=False),
        sa.Column("storage_key", sa.String(1024), nullable=True),
        sa.Column("ext", sa.String(32), nullable=True),
        sa.Column("schema_def", JSONB, nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("source_asset_id", sa.Integer(), sa.ForeignKey("assets.id"), nullable=True),
        sa.Column(
            "produced_by_node_id", sa.Integer(), sa.ForeignKey("pipeline_nodes.id"), nullable=True
        ),
    )

    op.create_foreign_key(
        "fk_pipeline_nodes_source_asset_id_assets",
        "pipeline_nodes", "assets", ["source_asset_id"], ["id"],
    )

    op.create_table(
        "asset_rows",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("row_idx", sa.Integer(), nullable=False),
        sa.Column("data", JSONB, nullable=False),
    )

    op.create_table(
        "pipeline_edges",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("pipeline_id", sa.Integer(), sa.ForeignKey("pipelines.id"), nullable=False),
        sa.Column("src_node_id", sa.Integer(), sa.ForeignKey("pipeline_nodes.id"), nullable=False),
        sa.Column("dst_node_id", sa.Integer(), sa.ForeignKey("pipeline_nodes.id"), nullable=False),
        sa.Column("dst_port", sa.String(64), nullable=False),
    )
    op.create_unique_constraint(
        "uq_pipeline_edges_dst_node_port", "pipeline_edges", ["dst_node_id", "dst_port"]
    )

    op.create_table(
        "node_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("node_id", sa.Integer(), sa.ForeignKey("pipeline_nodes.id"), nullable=False),
        sa.Column("status", sa.Enum(NodeRunStatus, name="noderunstatus"), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("output_kind", sa.String(32), nullable=True),
        sa.Column("output_ref", sa.Integer(), nullable=True),
        sa.Column("error", sa.String(2000), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("node_runs")
    op.drop_table("pipeline_edges")
    op.drop_table("asset_rows")
    op.drop_constraint("fk_pipeline_nodes_source_asset_id_assets", "pipeline_nodes", type_="foreignkey")
    op.drop_table("assets")
    op.drop_table("pipeline_nodes")
    op.drop_table("pipelines")
    op.drop_table("uploads")
    op.drop_index("ix_users_email", "users")
    op.drop_table("users")
    sa.Enum(name="noderunstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="assetorigin").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="assetstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="assetkind").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="uploadstatus").drop(op.get_bind(), checkfirst=True)
