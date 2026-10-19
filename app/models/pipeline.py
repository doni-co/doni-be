from datetime import datetime

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint, func, text
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
    __table_args__ = (
        # 한 노드의 포트(dst_port)에는 선이 하나만 들어올 수 있다 (예: join의 left 포트에 두 번 연결 금지).
        UniqueConstraint("dst_node_id", "dst_port", name="uq_pipeline_edges_dst_node_port"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    pipeline_id: Mapped[int] = mapped_column(ForeignKey("pipelines.id"))
    src_node_id: Mapped[int] = mapped_column(ForeignKey("pipeline_nodes.id"))
    dst_node_id: Mapped[int] = mapped_column(ForeignKey("pipeline_nodes.id"))
    dst_port: Mapped[str] = mapped_column(String(64), default="default")


class NodeRun(Base):
    """노드 하나를 실행한 기록. 파이프라인 전체를 묶는 Run 개념 없이, 노드 클릭 -> 실행 단위로
    독립적으로 생성된다 (화면에서 노드를 하나씩 클릭해서 transform을 실행하는 UX에 맞춘 구조)."""
    __tablename__ = "node_runs"
    __table_args__ = (
        # 노드 하나당 PENDING/RUNNING(진행 중) 실행은 동시에 1개만 허용 (retry 더블클릭 등 중복 실행 방지).
        # sa.Enum(NodeRunStatus)는 기본적으로 멤버 "이름"을 저장하므로(.value인 "pending"이 아니라
        # "PENDING") 아래 조건도 대문자여야 실제 컬럼 값과 맞는다.
        Index(
            "ix_node_runs_one_active_per_node", "node_id", unique=True,
            postgresql_where=text("status IN ('PENDING', 'RUNNING')"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    node_id: Mapped[int] = mapped_column(ForeignKey("pipeline_nodes.id"))
    status: Mapped[NodeRunStatus] = mapped_column(default=NodeRunStatus.PENDING)
    attempts: Mapped[int] = mapped_column(default=0)
    output_kind: Mapped[str | None] = mapped_column(String(32), nullable=True)
    output_ref: Mapped[int | None] = mapped_column(nullable=True)  # 결과 Asset.id
    error: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)  # RUNNING으로 선점된 시각
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)  # SUCCEEDED/FAILED로 끝난 시각
