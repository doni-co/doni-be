"""retry_node.py / delete_node.py 검증: FAILED만 retry 가능, 자식이 있거나 진행 중이면 삭제 거절,
삭제해도 그 노드가 만든 Asset은 보존된다."""
import pytest
from sqlalchemy.exc import IntegrityError

from app.domains.pipelines.errors import Conflict, NodeNotFound
from app.domains.pipelines.use_cases.delete_node import delete_node
from app.domains.pipelines.use_cases.retry_node import retry_node
from app.models.asset import Asset
from app.models.enums import NodeRunStatus
from app.models.pipeline import NodeRun, PipelineEdge, PipelineNode
from tests.domains.pipelines.fakes import FakeSession


# ---- retry ----

async def test_retry_requires_node():
    with pytest.raises(NodeNotFound):
        await retry_node(FakeSession(), node_id=999, owner_id=1, enqueue=lambda r: None)


async def test_retry_only_allowed_when_latest_run_failed():
    node = PipelineNode(id=1, pipeline_id=1, kind="select_columns", params={}, position={})
    succeeded_run = NodeRun(id=1, node_id=1, status=NodeRunStatus.SUCCEEDED, attempts=1)
    session = FakeSession(nodes=[node], runs=[succeeded_run])
    with pytest.raises(Conflict):
        await retry_node(session, node_id=1, owner_id=1, enqueue=lambda r: None)


async def test_retry_creates_new_pending_run_with_incremented_attempts():
    node = PipelineNode(id=1, pipeline_id=1, kind="select_columns", params={}, position={})
    failed_run = NodeRun(id=1, node_id=1, status=NodeRunStatus.FAILED, attempts=2, error="boom")
    session = FakeSession(nodes=[node], runs=[failed_run])

    result = await retry_node(session, node_id=1, owner_id=1, enqueue=lambda r: None)

    assert result["run"].status == NodeRunStatus.PENDING
    assert result["run"].attempts == 3
    assert result["run"] is not failed_run
    assert failed_run in session.runs  # 예전 실행 기록도 이력으로 남음


async def test_retry_double_submit_converted_to_conflict():
    """두 retry 요청이 동시에 '최신 실행은 FAILED'를 보고 통과하면, DB의 부분 유니크 인덱스가
    두 번째 INSERT를 막는다. 이 테스트는 그 IntegrityError가 Conflict(409)로 변환되는지만 본다
    (실제 동시성 레이스는 FakeSession으로 재현할 수 없어 commit()을 직접 실패시킨다)."""
    node = PipelineNode(id=1, pipeline_id=1, kind="select_columns", params={}, position={})
    failed_run = NodeRun(id=1, node_id=1, status=NodeRunStatus.FAILED, attempts=1)
    session = FakeSession(nodes=[node], runs=[failed_run])

    async def failing_commit():
        raise IntegrityError("ix_node_runs_one_active_per_node", {}, Exception())

    session.commit = failing_commit  # type: ignore[method-assign]

    with pytest.raises(Conflict):
        await retry_node(session, node_id=1, owner_id=1, enqueue=lambda r: None)


# ---- delete ----

async def test_delete_requires_node():
    with pytest.raises(NodeNotFound):
        await delete_node(FakeSession(), node_id=999)


async def test_delete_rejected_when_node_has_children():
    parent = PipelineNode(id=1, pipeline_id=1, kind="select_columns", params={}, position={})
    child = PipelineNode(id=2, pipeline_id=1, kind="rename_columns", params={}, position={})
    edge = PipelineEdge(id=1, pipeline_id=1, src_node_id=1, dst_node_id=2, dst_port="input")
    session = FakeSession(nodes=[parent, child], edges=[edge])
    with pytest.raises(Conflict):
        await delete_node(session, node_id=1)


@pytest.mark.parametrize("status", [NodeRunStatus.PENDING, NodeRunStatus.RUNNING])
async def test_delete_rejected_when_in_progress(status):
    node = PipelineNode(id=1, pipeline_id=1, kind="select_columns", params={}, position={})
    run = NodeRun(id=1, node_id=1, status=status, attempts=1)
    session = FakeSession(nodes=[node], runs=[run])
    with pytest.raises(Conflict):
        await delete_node(session, node_id=1)


async def test_delete_leaf_failed_node_preserves_its_asset():
    source = PipelineNode(id=1, pipeline_id=1, kind="source", params={}, position={}, source_asset_id=10)
    node = PipelineNode(id=2, pipeline_id=1, kind="select_columns", params={}, position={})
    incoming_edge = PipelineEdge(id=1, pipeline_id=1, src_node_id=1, dst_node_id=2, dst_port="input")
    run = NodeRun(id=1, node_id=2, status=NodeRunStatus.FAILED, attempts=1)
    asset = Asset(id=20, owner_id=1, name="select_columns 결과", produced_by_node_id=2)
    session = FakeSession(nodes=[source, node], edges=[incoming_edge], runs=[run], assets=[asset])

    await delete_node(session, node_id=2)

    assert node not in session.nodes
    assert incoming_edge not in session.edges
    assert run not in session.runs
    assert asset in session.assets  # Asset 자체는 보존
    assert asset.produced_by_node_id is None  # 더 이상 없는 노드를 가리키지 않음
