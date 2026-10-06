from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import NodeRunStatus, RunStatus


class Pipeline(Base):
    __tablename__ = "pipelines"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(255))


class PipelineNode(Base):
    __tablename__ = "pipeline_nodes"

    id: Mapped[int] = mapped_column(primary_key=True)
    pipeline_id: Mapped[int] = mapped_column(ForeignKey("pipelines.id"))
    kind: Mapped[str] = mapped_column(String(64))       # transforms.registry 키와 매칭
    params: Mapped[dict] = mapped_column(JSONB, default=dict)
    position: Mapped[dict] = mapped_column(JSONB, default=dict)


class PipelineEdge(Base):
    __tablename__ = "pipeline_edges"

    id: Mapped[int] = mapped_column(primary_key=True)
    pipeline_id: Mapped[int] = mapped_column(ForeignKey("pipelines.id"))
    src_node_id: Mapped[int] = mapped_column(ForeignKey("pipeline_nodes.id"))
    dst_node_id: Mapped[int] = mapped_column(ForeignKey("pipeline_nodes.id"))
    dst_port: Mapped[str] = mapped_column(String(64), default="default")


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    pipeline_id: Mapped[int] = mapped_column(ForeignKey("pipelines.id"))
    status: Mapped[RunStatus] = mapped_column(default=RunStatus.PENDING)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)
    error: Mapped[str | None] = mapped_column(String(2000), nullable=True)


class NodeRun(Base):
    __tablename__ = "node_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("pipeline_runs.id"))
    node_id: Mapped[int] = mapped_column(ForeignKey("pipeline_nodes.id"))
    status: Mapped[NodeRunStatus] = mapped_column(default=NodeRunStatus.PENDING)
    attempts: Mapped[int] = mapped_column(default=0)
    input_fingerprint: Mapped[str | None] = mapped_column(String(128), nullable=True)
    output_kind: Mapped[str | None] = mapped_column(String(32), nullable=True)  # dataset|media_set
    output_ref: Mapped[int | None] = mapped_column(nullable=True)  # 결과 Dataset/MediaSet id
    error: Mapped[str | None] = mapped_column(String(2000), nullable=True)
