from pydantic import BaseModel, ConfigDict

from app.models.enums import AssetKind, AssetStatus


class AssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    kind: AssetKind
    status: AssetStatus
    row_count: int | None = None


class AssetRowsOut(BaseModel):
    columns: list[str]
    rows: list[dict]
    total: int
