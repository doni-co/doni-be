from pydantic import BaseModel, ConfigDict

from app.models.enums import NodeRunStatus


class PipelineCreate(BaseModel):
    name: str


class NodeCreate(BaseModel):
    kind: str
    params: dict = {}
    position: dict = {}
    source_asset_id: int | None = None  # kind="source"일 때 업로드된 Asset을 가리킴


class EdgeCreate(BaseModel):
    src_node_id: int
    dst_node_id: int
    dst_port: str = "default"


class NodeRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    node_id: int
    status: NodeRunStatus
    output_kind: str | None
    output_ref: int | None
    error: str | None
