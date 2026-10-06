from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.domains.media.schemas import MediaSetOut
from app.domains.media.service import get_media_set

router = APIRouter(prefix="/media-sets", tags=["media"])


@router.get("/{media_set_id}", response_model=MediaSetOut)
async def get_route(media_set_id: int, session: AsyncSession = Depends(get_session)):
    media_set = await get_media_set(session, media_set_id)
    if media_set is None:
        raise HTTPException(404)
    return media_set
