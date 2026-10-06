from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import AssetStatus


class MediaSet(Base):
    __tablename__ = "media_sets"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(255))
    status: Mapped[AssetStatus] = mapped_column(default=AssetStatus.UPLOADED)

    files: Mapped[list["MediaFile"]] = relationship(back_populates="media_set")


class MediaFile(Base):
    __tablename__ = "media_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    media_set_id: Mapped[int] = mapped_column(ForeignKey("media_sets.id"))
    storage_key: Mapped[str] = mapped_column(String(1024))
    original_name: Mapped[str] = mapped_column(String(512))
    ext: Mapped[str] = mapped_column(String(32))
    size_bytes: Mapped[int] = mapped_column(default=0)

    media_set: Mapped["MediaSet"] = relationship(back_populates="files")
