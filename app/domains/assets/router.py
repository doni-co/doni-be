from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.domains.assets.schemas import AssetOut, AssetRowsOut
from app.domains.assets.service import get_asset, get_rows

router = APIRouter(prefix="/assets", tags=["assets"])


@router.get("/{asset_id}", response_model=AssetOut)
async def get_route(asset_id: int, session: AsyncSession = Depends(get_session)):
    asset = await get_asset(session, asset_id)
    if asset is None:
        raise HTTPException(404)
    return asset


@router.get("/{asset_id}/rows", response_model=AssetRowsOut)
async def get_rows_route(asset_id: int, session: AsyncSession = Depends(get_session)):
    """캔버스 하단 "미리보기" 테이블이 호출하는 엔드포인트."""
    asset = await get_asset(session, asset_id)
    if asset is None:
        raise HTTPException(404)
    columns, rows = await get_rows(session, asset_id)
    return AssetRowsOut(columns=columns, rows=rows, total=len(rows))
