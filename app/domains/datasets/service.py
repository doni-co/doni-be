from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import AssetOrigin, AssetStatus
from app.models.dataset import Dataset


async def register_dataset(
    session: AsyncSession,
    owner_id: int,
    name: str,
    storage_key: str,
    origin: AssetOrigin = AssetOrigin.UPLOAD,
) -> Dataset:
    dataset = Dataset(
        owner_id=owner_id, name=name, storage_key=storage_key,
        status=AssetStatus.READY, origin=origin,
    )
    session.add(dataset)
    await session.commit()
    await session.refresh(dataset)
    return dataset


async def get_dataset(session: AsyncSession, dataset_id: int) -> Dataset | None:
    """다른 도메인(pipelines 등)은 이 함수로만 Dataset에 접근한다 (직접 쿼리 금지).
    온톨로지 쪽에서 Dataset을 가져다 쓸 때도 이 함수가 접점이 된다."""
    return await session.get(Dataset, dataset_id)
