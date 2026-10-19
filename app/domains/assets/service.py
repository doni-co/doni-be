"""Asset(원본/결과 메타데이터) + AssetRow(정형 행 데이터) 전담 쿼리.
다른 도메인(ingestion, pipelines)은 반드시 이 함수들을 통해서만 Asset/AssetRow에 접근한다
(직접 쿼리 금지 — 나중에 pipelines를 별도 서버로 분리할 때 이 규칙이 분리 난이도를 결정한다)."""
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Asset, AssetRow
from app.models.enums import AssetKind, AssetOrigin, AssetStatus


async def register_asset(
    session: AsyncSession,
    owner_id: int,
    name: str,
    kind: AssetKind,
    storage_key: str | None = None,
    ext: str | None = None,
    origin: AssetOrigin = AssetOrigin.UPLOAD,
    source_asset_id: int | None = None,
    produced_by_node_id: int | None = None,
) -> Asset:
    asset = Asset(
        owner_id=owner_id, name=name, kind=kind, status=AssetStatus.READY, origin=origin,
        storage_key=storage_key, ext=ext,
        source_asset_id=source_asset_id, produced_by_node_id=produced_by_node_id,
    )
    session.add(asset)
    await session.commit()
    await session.refresh(asset)
    return asset


async def get_asset(session: AsyncSession, asset_id: int) -> Asset | None:
    return await session.get(Asset, asset_id)


async def save_rows(session: AsyncSession, asset_id: int, columns: list[str], rows: list[dict]) -> None:
    """transform/join/union 결과 행을 저장하고, Asset의 schema_def/row_count를 채운다.
    [파일]과 [파이프라인빌더]의 데이터는 갱신하지 않는다(갱신은 온톨로지). 한 Asset에는 한 번만 저장할 수 있고,
    다시 실행하면 새 Asset을 만들어 저장해야 한다."""
    asset = await session.get(Asset, asset_id)
    if asset is None:
        raise ValueError(f"asset not found: {asset_id}")
    if asset.row_count is not None:
        raise ValueError(f"asset {asset_id} already has data; assets are immutable")
    asset.schema_def = {"columns": columns}
    asset.row_count = len(rows)

    for idx, row in enumerate(rows):
        session.add(AssetRow(asset_id=asset_id, row_idx=idx, data=row))

    await session.commit()


async def clear_produced_by_node(session: AsyncSession, node_id: int) -> None:
    """노드 삭제 시 그 노드가 만든 Asset은 보존하되, 더 이상 존재하지 않는 노드를 가리키지 않게 한다
    (pipelines/use_cases/delete_node.py가 노드를 지우기 직전에 호출)."""
    await session.execute(
        update(Asset).where(Asset.produced_by_node_id == node_id).values(produced_by_node_id=None)
    )
    await session.commit()


async def get_rows(session: AsyncSession, asset_id: int) -> tuple[list[str], list[dict]]:
    """노드 실행(use_cases/execute_node.py)이 입력 데이터를 불러올 때 쓰는 "load" 함수."""
    asset = await session.get(Asset, asset_id)
    columns = (asset.schema_def or {}).get("columns", [])

    result = await session.execute(
        select(AssetRow).where(AssetRow.asset_id == asset_id).order_by(AssetRow.row_idx)
    )
    rows = [r.data for r in result.scalars().all()]
    return columns, rows
