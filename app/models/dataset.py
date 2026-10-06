from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import AssetOrigin, AssetStatus


class Dataset(Base):
    """정형 데이터. 업로드로 생기거나(origin=UPLOAD) 노드 실행 결과로 생긴다(origin=NODE_OUTPUT).
    온톨로지 쪽(오브젝트 타입 매핑)과의 접점이 되는 테이블이다."""
    __tablename__ = "datasets"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(255))
    schema_def: Mapped[dict] = mapped_column(JSONB, default=dict)  # 컬럼명 -> 타입
    storage_key: Mapped[str] = mapped_column(String(1024))
    row_count: Mapped[int] = mapped_column(default=0)
    status: Mapped[AssetStatus] = mapped_column(default=AssetStatus.UPLOADED)
    origin: Mapped[AssetOrigin] = mapped_column(default=AssetOrigin.UPLOAD)
