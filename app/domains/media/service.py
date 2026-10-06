from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import AssetStatus
from app.models.media import MediaFile, MediaSet


async def register_media_set(session: AsyncSession, owner_id: int, name: str, storage_key: str) -> MediaSet:
    media_set = MediaSet(owner_id=owner_id, name=name, status=AssetStatus.READY)
    session.add(media_set)
    await session.flush()

    ext = name.rsplit(".", 1)[-1] if "." in name else ""
    session.add(MediaFile(media_set_id=media_set.id, storage_key=storage_key, original_name=name, ext=ext))
    await session.commit()
    await session.refresh(media_set)
    return media_set


async def get_media_set(session: AsyncSession, media_set_id: int) -> MediaSet | None:
    """다른 도메인(pipelines 등)은 이 함수로만 MediaSet에 접근한다 (직접 쿼리 금지)."""
    return await session.get(MediaSet, media_set_id)
