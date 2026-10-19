from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import AssetKind, AssetStatus


class AssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    kind: AssetKind
    status: AssetStatus
    row_count: int | None = None
    ext: str | None = None
    size_bytes: int | None = None
    content_type: str | None = None
    created_at: datetime | None = None


class AssetRowsOut(BaseModel):
    columns: list[str]
    rows: list[dict]
    total: int
