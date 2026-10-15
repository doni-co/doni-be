"""[파일] 목록 API: 응답 형태와 쿼리 파라미터 검증. 정렬/필터 SQL은 DB가 있어야 확인할 수 있어 compose 검증에서 본다."""
from datetime import UTC, datetime

import pytest

from app.db.session import get_session
from app.domains.assets import router as assets_router
from app.main import app
from app.models.asset import Asset
from app.models.enums import AssetKind, AssetStatus


@pytest.fixture(autouse=True)
def no_db():
    app.dependency_overrides[get_session] = lambda: None
    yield
    app.dependency_overrides.pop(get_session, None)


@pytest.fixture
def seen(monkeypatch):
    args = []

    async def fake_list(session, owner_id, limit, offset):
        args.append((owner_id, limit, offset))
        return [
            Asset(id=2, name="sales (2).csv", kind=AssetKind.DATASET, status=AssetStatus.READY, row_count=3,
                  ext="csv", size_bytes=120, content_type="text/csv", sha256="x" * 64,
                  created_at=datetime(2026, 9, 15, 13, 15, tzinfo=UTC)),
            Asset(id=1, name="report.pdf", kind=AssetKind.MEDIASET, status=AssetStatus.READY, row_count=None,
                  ext="pdf", size_bytes=999, content_type="application/pdf",
                  created_at=datetime(2026, 9, 14, 9, 0, tzinfo=UTC)),
        ]

    monkeypatch.setattr(assets_router, "list_uploaded_assets", fake_list)
    return args


async def test_list_response_shape(client, seen):
    resp = await client.get("/assets")
    assert resp.status_code == 200
    items = resp.json()
    assert [i["id"] for i in items] == [2, 1]
    first = items[0]
    assert first["name"] == "sales (2).csv"
    assert first["kind"] == "dataset"
    assert first["ext"] == "csv"
    assert first["size_bytes"] == 120
    assert first["content_type"] == "text/csv"
    assert first["created_at"].startswith("2026-09-15T13:15")
    assert "sha256" not in first  # 무결성 확인용이라 응답에 넣지 않는다
    assert items[1]["kind"] == "mediaset" and items[1]["row_count"] is None


async def test_list_defaults_and_params(client, seen):
    await client.get("/assets")
    await client.get("/assets", params={"owner_id": 7, "limit": 5, "offset": 10})
    assert seen == [(1, 100, 0), (7, 5, 10)]


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 501}, {"offset": -1}])
async def test_list_rejects_bad_paging(client, seen, params):
    resp = await client.get("/assets", params=params)
    assert resp.status_code == 422
    assert seen == []


async def test_list_route_does_not_shadow_asset_detail(client, monkeypatch):
    async def fake_get_asset(session, asset_id):
        return Asset(id=asset_id, name="a.csv", kind=AssetKind.DATASET, status=AssetStatus.READY)

    monkeypatch.setattr(assets_router, "get_asset", fake_get_asset)
    resp = await client.get("/assets/5")
    assert resp.status_code == 200
    assert resp.json()["id"] == 5
