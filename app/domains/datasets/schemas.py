from pydantic import BaseModel, ConfigDict

from app.models.enums import AssetStatus


class DatasetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    status: AssetStatus
    row_count: int
