from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import NodeRunStatus


class Pipeline(Base):
    __tablename__ = "pipelines"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(255))


class PipelineNode(Base):
    """캔버스에 올라간 노드 하나(업로드 박스 포함). kind가 "source"면 업로드 원본 자체를 가리키는
    노드이고, 그 외(예: "filter", "join")는 nodes/registry.py의 key와 매칭된다."""
    __tablename__ = "pipeline_nodes"

    id: Mapped[int] = mapped_column(primary_key=True)
    pipeline_id: Mapped[int] = mapped_column(ForeignKey("pipelines.id"))
    kind: Mapped[str] = mapped_column(String(64))
    params: Mapped[dict] = mapped_column(JSONB, default=dict)
    position: Mapped[dict] = mapped_column(JSONB, default=dict)

    # source 노드(kind="source")는 업로드된 Asset을 직접 가리킨다.
    source_asset_id: Mapped[int | None] = mapped_column(ForeignKey("assets.id"), nullable=True)


class PipelineEdge(Base):
    __tablename__ = "pipeline_edges"

    id: Mapped[int] = mapped_column(primary_key=True)
    pipeline_id: Mapped[int] = mapped_column(ForeignKey("pipelines.id"))
    src_node_id: Mapped[int] = mapped_column(ForeignKey("pipeline_nodes.id"))
    dst_node_id: Mapped[int] = mapped_column(ForeignKey("pipeline_nodes.id"))
    dst_port: Mapped[str] = mapped_column(String(64), default="default")


class NodeRun(Base):
    """노드 하나를 실행한 기록. 파이프라인 전체를 묶는 Run 개념 없이, 노드 클릭 -> 실행 단위로
    독립적으로 생성된다 (화면에서 노드를 하나씩 클릭해서 transform을 실행하는 UX에 맞춘 구조)."""
    __tablename__ = "node_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    node_id: Mapped[int] = mapped_column(ForeignKey("pipeline_nodes.id"))
    status: Mapped[NodeRunStatus] = mapped_column(default=NodeRunStatus.PENDING)
    attempts: Mapped[int] = mapped_column(default=0)
    output_kind: Mapped[str | None] = mapped_column(String(32), nullable=True)
    output_ref: Mapped[int | None] = mapped_column(nullable=True)  # 결과 Asset.id
    error: Mapped[str | None] = mapped_column(String(2000), nullable=True)
