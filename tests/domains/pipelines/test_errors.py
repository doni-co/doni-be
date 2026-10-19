"""도메인 예외(errors.py)가 main.py의 핸들러를 거쳐 올바른 HTTP 코드로 나가는지,
실제 라우터를 통해 확인한다(httpx ASGI 클라이언트 + get_session 의존성을 FakeSession으로 교체)."""
import pytest

from app.db.session import get_session
from app.domains.pipelines.tasks import execute_node_task
from app.main import app
from app.models.pipeline import PipelineNode
from tests.domains.pipelines.fakes import FakeSession


@pytest.fixture
def fake_session():
    session = FakeSession()

    async def _override():
        yield session

    app.dependency_overrides[get_session] = _override
    yield session
    app.dependency_overrides.pop(get_session, None)


async def test_unknown_kind_returns_422(client, fake_session):
    resp = await client.post(
        "/pipelines/nodes/transform",
        json={"input_node_id": 1, "kind": "not_a_real_kind", "params": {}, "position": {}},
    )
    assert resp.status_code == 422
    assert "unknown transform" in resp.json()["detail"]


async def test_retry_on_missing_node_returns_404(client, fake_session):
    resp = await client.post("/pipelines/nodes/999/retry")
    assert resp.status_code == 404


async def test_create_transform_succeeds_and_persists_node_even_if_queue_unreachable(client, fake_session, monkeypatch):
    fake_session.nodes.append(
        PipelineNode(id=1, pipeline_id=1, kind="source", params={}, position={}, source_asset_id=10)
    )

    def fake_delay(run_id, owner_id):
        raise RuntimeError("no broker in test env")

    monkeypatch.setattr(execute_node_task, "delay", fake_delay)

    resp = await client.post(
        "/pipelines/nodes/transform",
        json={"input_node_id": 1, "kind": "select_columns", "params": {"columns": ["a"]}, "position": {}},
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["node"]["kind"] == "select_columns"
    # 큐에 못 넣었어도 노드는 저장되고, 그 실행만 FAILED로 표시된다 (노드 보존이 핵심 요구사항).
    assert body["run"]["status"] == "failed"
