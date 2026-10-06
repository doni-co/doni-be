"""데이터 출력 > 새로운 데이터셋: 노드 결과를 최종 Dataset으로 확정한다.
Transform이 아니라 pipelines 자체의 유스케이스 (입력 하나를 받아 결과를 "확정"만 함)."""
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.datasets.service import get_dataset, register_dataset
from app.models.enums import AssetOrigin


async def export_as_new_dataset(session: AsyncSession, owner_id: int, source_dataset_id: int, name: str):
    source = await get_dataset(session, source_dataset_id)
    if source is None:
        raise ValueError("source dataset not found")
    return await register_dataset(
        session, owner_id=owner_id, name=name,
        storage_key=source.storage_key, origin=AssetOrigin.NODE_OUTPUT,
    )
