from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import AssetKind, UploadStatus


class Upload(Base):
    """업로드된 파일의 공통 기록. storage.save 직후, Asset으로 분류되기 전에 먼저 생성된다.
    분류가 실패하거나 이후 단계에서 에러가 나도 "이 파일이 들어왔다"는 흔적이 여기 남는다."""
    __tablename__ = "uploads"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    original_filename: Mapped[str] = mapped_column(String(512))
    storage_key: Mapped[str] = mapped_column(String(1024))
    status: Mapped[UploadStatus] = mapped_column(default=UploadStatus.STORED)

    asset_kind: Mapped[AssetKind | None] = mapped_column(nullable=True)
    asset_id: Mapped[int | None] = mapped_column(nullable=True)

    error: Mapped[str | None] = mapped_column(String(2000), nullable=True)
