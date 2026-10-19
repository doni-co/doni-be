from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.enums import NodeRunStatus


class PipelineCreate(BaseModel):
    name: str


class NodeCreate(BaseModel):
    kind: str
    params: dict = {}
    position: dict = {}
    source_asset_id: int | None = None  # kind="source"일 때 업로드된 Asset을 가리킴


class TransformNodeCreate(BaseModel):
    input_node_id: int
    kind: str
    params: dict = {}
    position: dict = {}


class JoinNodeCreate(BaseModel):
    left_node_id: int
    right_node_id: int
    params: dict = {}
    position: dict = {}


class UnionNodeCreate(BaseModel):
    node_ids: list[int]
    position: dict = {}

    @field_validator("node_ids")
    @classmethod
    def _exactly_two(cls, v: list[int]) -> list[int]:
        if len(v) != 2:
            raise ValueError("union은 정확히 2개의 node_ids가 필요합니다")
        return v


class NodeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    pipeline_id: int
    kind: str
    params: dict
    position: dict
    source_asset_id: int | None


class EdgeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    src_node_id: int
    dst_node_id: int
    dst_port: str


class NodeRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    node_id: int
    status: NodeRunStatus
    attempts: int
    output_kind: str | None
    output_ref: int | None
    error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class NodeWithRunOut(BaseModel):
    node: NodeOut
    edges: list[EdgeOut]
    run: NodeRunOut


class GraphOut(BaseModel):
    nodes: list[NodeOut]
    edges: list[EdgeOut]
    runs: dict[int, NodeRunOut]  # node_id -> 그 노드의 최신 NodeRun
