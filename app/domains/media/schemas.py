from pydantic import BaseModel, ConfigDict

from app.models.enums import AssetStatus


class MediaSetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    status: AssetStatus
