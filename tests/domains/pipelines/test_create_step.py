"""POST /pipelines/nodes/transform|join|union 의 공통 로직(create_step.py) 검증.
요청 거절(422/404/409)이 아무것도 저장하지 않는지, 큐 등록 실패해도 노드/실행 기록이
보존되는지(핵심 요구사항)를 FakeSession(tests/domains/pipelines/fakes.py)으로 확인한다."""
import pytest

from app.domains.pipelines.errors import Conflict, InvalidRequest, NodeNotFound
from app.domains.pipelines.use_cases.create_step import (
    create_join_step,
    create_transform_step,
    create_union_step,
)
from app.models.enums import NodeRunStatus
from app.models.pipeline import NodeRun, PipelineNode
from tests.domains.pipelines.fakes import FakeSession


def _source_node(node_id=1, asset_id=10) -> PipelineNode:
    return PipelineNode(id=node_id, pipeline_id=1, kind="source", params={}, position={}, source_asset_id=asset_id)


def _succeeded_node(node_id=1) -> tuple[PipelineNode, NodeRun]:
    node = PipelineNode(id=node_id, pipeline_id=1, kind="select_columns", params={}, position={})
    run = NodeRun(id=100 + node_id, node_id=node_id, status=NodeRunStatus.SUCCEEDED, attempts=1, output_ref=99)
    return node, run


# ---- DB를 건드리기 전에 끝나는 검증 (session 없이도 통과해야 함) ----

async def test_unknown_kind_rejected():
    with pytest.raises(InvalidRequest, match="unknown transform"):
        await create_transform_step(
            object(), input_node_id=1, kind="not_a_real_kind", params={}, position={},
            owner_id=1, enqueue=lambda run_id: None,
        )


async def test_transform_endpoint_rejects_join_kind():
    with pytest.raises(InvalidRequest, match="join"):
        await create_transform_step(
            object(), input_node_id=1, kind="join", params={}, position={},
            owner_id=1, enqueue=lambda run_id: None,
        )


async def test_invalid_params_rejected():
    with pytest.raises(InvalidRequest):
        await create_transform_step(
            object(), input_node_id=1, kind="select_columns", params={"columns": []},  # min_length=1 위반
            position={}, owner_id=1, enqueue=lambda run_id: None,
        )


# ---- 정상 생성 ----

async def test_transform_from_source_creates_node_edge_pending_run():
    session = FakeSession(nodes=[_source_node()])
    result = await create_transform_step(
        session, input_node_id=1, kind="select_columns", params={"columns": ["a", "b"]}, position={"x": 1},
        owner_id=1, enqueue=lambda run_id: None,
    )
    assert result["node"].kind == "select_columns"
    assert result["node"] in session.nodes
    assert len(result["edges"]) == 1
    assert result["edges"][0].src_node_id == 1
    assert result["edges"][0].dst_port == "input"
    assert result["run"].status == NodeRunStatus.PENDING
    assert result["run"] in session.runs


async def test_join_uses_left_right_ports():
    left, left_run = _succeeded_node(1)
    right, right_run = _succeeded_node(2)
    session = FakeSession(nodes=[left, right], runs=[left_run, right_run])
    result = await create_join_step(
        session, left_node_id=1, right_node_id=2, params={"left_key": "a", "right_key": "a"},
        position={}, owner_id=1, enqueue=lambda run_id: None,
    )
    ports = {(e.src_node_id, e.dst_port) for e in result["edges"]}
    assert ports == {(1, "left"), (2, "right")}


async def test_union_requires_exactly_two_inputs():
    a, a_run = _succeeded_node(1)
    b, b_run = _succeeded_node(2)
    session = FakeSession(nodes=[a, b], runs=[a_run, b_run])
    result = await create_union_step(
        session, node_ids=[1, 2], params={}, position={}, owner_id=1, enqueue=lambda run_id: None,
    )
    assert len(result["edges"]) == 2


# ---- 거절 (아무것도 저장하지 않음) ----

async def test_missing_input_node_returns_404_and_saves_nothing():
    src = _source_node()
    session = FakeSession(nodes=[src])
    with pytest.raises(NodeNotFound):
        await create_transform_step(
            session, input_node_id=999, kind="select_columns", params={"columns": ["a"]},
            position={}, owner_id=1, enqueue=lambda run_id: None,
        )
    assert session.nodes == [src]  # 새 노드 안 생김
    assert session.runs == []


async def test_input_not_ready_returns_409():
    upstream = PipelineNode(id=1, pipeline_id=1, kind="select_columns", params={}, position={})
    session = FakeSession(nodes=[upstream])  # 최신 SUCCEEDED 실행이 없음
    with pytest.raises(Conflict):
        await create_transform_step(
            session, input_node_id=1, kind="rename_columns", params={"mapping": {"a": "b"}},
            position={}, owner_id=1, enqueue=lambda run_id: None,
        )
    assert session.nodes == [upstream]
    assert session.runs == []


# ---- 큐 등록 실패: 노드/실행 기록은 보존되고, 그 실행만 즉시 FAILED (핵심 요구사항) ----

async def test_enqueue_failure_keeps_node_but_marks_run_failed():
    session = FakeSession(nodes=[_source_node()])

    def boom(run_id: int) -> None:
        raise RuntimeError("redis down")

    result = await create_transform_step(
        session, input_node_id=1, kind="select_columns", params={"columns": ["a"]}, position={},
        owner_id=1, enqueue=boom,
    )
    assert result["node"] in session.nodes  # 노드는 그대로 남음
    assert result["run"].status == NodeRunStatus.FAILED
    assert "redis down" in result["run"].error
