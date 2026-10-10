from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import AssetKind, AssetOrigin, AssetStatus


class Asset(Base):
    """원본 업로드(media_set/dataset)와 노드 실행 결과(항상 dataset)를 모두 표현하는 단일 테이블.
    업로드 파일 하나당 Asset 하나(1:1)이므로 MediaSet/Dataset을 별도 테이블로 나누지 않는다.
    온톨로지 모듈이 Entity 타입으로 승격시킬 때도 이 테이블(kind=dataset)을 참조하게 된다."""
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(255))
    kind: Mapped[AssetKind]
    status: Mapped[AssetStatus] = mapped_column(default=AssetStatus.UPLOADED)
    origin: Mapped[AssetOrigin] = mapped_column(default=AssetOrigin.UPLOAD)

    storage_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)  # Garage 경로 (원본이 있는 경우)
    ext: Mapped[str | None] = mapped_column(String(32), nullable=True)

    schema_def: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # kind=dataset일 때만
    row_count: Mapped[int | None] = mapped_column(nullable=True)

    # lineage: 이 Asset이 어느 Asset/어느 노드에서 파생됐는지 (origin=node_output일 때 채워짐)
    source_asset_id: Mapped[int | None] = mapped_column(ForeignKey("assets.id"), nullable=True)
    produced_by_node_id: Mapped[int | None] = mapped_column(ForeignKey("pipeline_nodes.id"), nullable=True)


class AssetRow(Base):
    """kind=dataset인 Asset의 실제 행 데이터. 정형 업로드 결과든, PDF/이미지 추출 결과든,
    join/union 결과든 전부 여기 JSONB 행으로 담긴다. 컬럼명은 Asset.schema_def가 정의한다."""
    __tablename__ = "asset_rows"

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"))
    row_idx: Mapped[int]
    data: Mapped[dict] = mapped_column(JSONB)
