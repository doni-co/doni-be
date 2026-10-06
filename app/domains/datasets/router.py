from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.domains.datasets.schemas import DatasetOut
from app.domains.datasets.service import get_dataset

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.get("/{dataset_id}", response_model=DatasetOut)
async def get_route(dataset_id: int, session: AsyncSession = Depends(get_session)):
    dataset = await get_dataset(session, dataset_id)
    if dataset is None:
        raise HTTPException(404)
    return dataset
