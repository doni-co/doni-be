from pydantic import BaseModel, ConfigDict

from app.models.enums import NodeRunStatus, RunStatus


class PipelineCreate(BaseModel):
    name: str


class NodeCreate(BaseModel):
    kind: str
    params: dict = {}
    position: dict = {}


class EdgeCreate(BaseModel):
    src_node_id: int
    dst_node_id: int
    dst_port: str = "default"


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: RunStatus


class NodeRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    node_id: int
    status: NodeRunStatus
    output_kind: str | None
    output_ref: int | None
    error: str | None
