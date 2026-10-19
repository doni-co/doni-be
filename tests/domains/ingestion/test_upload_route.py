"""업로드 라우트: 크기 제한, 파일명 검사, 예외 → HTTP 상태 매핑. DB/스토리지 없이 upload_file을 가짜로 바꿔 확인한다."""
import pytest

from app.db.session import get_session
from app.domains.ingestion import router as ingestion_router
from app.domains.ingestion.classifier import UnsupportedFileType
from app.domains.ingestion.parsers import InvalidFileContent
from app.main import app


@pytest.fixture(autouse=True)
def no_db():
    app.dependency_overrides[get_session] = lambda: None
    yield
    app.dependency_overrides.pop(get_session, None)


@pytest.fixture
def calls(monkeypatch):
    recorded = []

    async def fake_upload_file(session, owner_id, filename, data, content_type=None):
        recorded.append({"owner_id": owner_id, "filename": filename, "data": data, "content_type": content_type})
        return {"upload_id": 1, "asset_id": 2, "kind": "dataset"}

    monkeypatch.setattr(ingestion_router, "upload_file", fake_upload_file)
    return recorded


async def test_upload_passes_bytes_name_and_content_type(client, calls):
    resp = await client.post("/uploads", files={"file": ("sales.csv", b"a,b\n1,2\n", "text/csv")})
    assert resp.status_code == 200
    assert resp.json() == {"upload_id": 1, "asset_id": 2, "kind": "dataset"}
    assert calls == [{"owner_id": 1, "filename": "sales.csv", "data": b"a,b\n1,2\n", "content_type": "text/csv"}]


async def test_path_in_filename_is_stripped(client, calls):
    await client.post("/uploads", files={"file": ("../../x.csv", b"a\n1\n", "text/csv")})
    assert calls[0]["filename"] == "x.csv"


async def test_file_over_limit_is_413_and_nothing_is_processed(client, calls, monkeypatch):
    monkeypatch.setattr(ingestion_router, "MAX_UPLOAD_BYTES", 10)
    resp = await client.post("/uploads", files={"file": ("big.csv", b"x" * 11)})
    assert resp.status_code == 413
    assert calls == []


async def test_file_exactly_at_limit_is_accepted(client, calls, monkeypatch):
    monkeypatch.setattr(ingestion_router, "MAX_UPLOAD_BYTES", 10)
    resp = await client.post("/uploads", files={"file": ("ok.csv", b"x" * 10)})
    assert resp.status_code == 200


def test_limit_is_100mb():
    assert ingestion_router.MAX_UPLOAD_BYTES == 100 * 1024 * 1024  # 프론트 업로드 창 안내와 같다


@pytest.mark.parametrize("name", ["..", "."])
async def test_invalid_filename_is_400(client, calls, name):
    resp = await client.post("/uploads", files={"file": (name, b"x")})
    assert resp.status_code == 400
    assert calls == []


@pytest.mark.parametrize(("error", "message"), [
    (UnsupportedFileType(".zip"), "unsupported file type"),
    (InvalidFileContent("row 2: 3 fields, header has 2"), "invalid file content"),
])
async def test_upload_errors_are_400(client, monkeypatch, error, message):
    async def failing(*args, **kwargs):
        raise error

    monkeypatch.setattr(ingestion_router, "upload_file", failing)
    resp = await client.post("/uploads", files={"file": ("a.csv", b"x")})
    assert resp.status_code == 400
    assert message in resp.json()["detail"]
