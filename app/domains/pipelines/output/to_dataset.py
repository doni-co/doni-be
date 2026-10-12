"""데이터 출력 > 새로운 데이터셋: 노드 결과(Asset)를 사용자가 보는 "확정된 데이터셋"으로 표시한다.
Transform이 아니라 pipelines 자체의 유스케이스: 계산이 아니라 "이미 계산된 결과를 출력물로 확정"하는 동작."""
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.assets.service import get_asset


async def export_as_new_dataset(session: AsyncSession, source_asset_id: int, name: str) -> dict:
    source = await get_asset(session, source_asset_id)
    if source is None:
        raise ValueError("source asset not found")
    # 현재는 이름만 바꾼 뷰를 제공한다. 물리적으로 새 Asset을 복제할지는 UX 확정 후 결정.
    return {"asset_id": source.id, "name": name, "row_count": source.row_count}
