"""데이터 출력 > 새로운 Entity 타입: Asset(kind=dataset)을 온톨로지 Entity 타입으로 등록.
온톨로지 모듈이 아직 설계되지 않아 지금은 자리만 잡아둔 스텁."""
from sqlalchemy.ext.asyncio import AsyncSession


async def export_as_entity_type(session: AsyncSession, source_asset_id: int, entity_type_name: str):
    raise NotImplementedError  # TODO: 온톨로지 모듈 설계 후 연결
