"""DB/스토리지 없이 도는 테스트: 저장 키 규칙(순수 함수)과, upload_file이 같은 이름을 덮어쓰지 않는지."""
import io

import pytest

from app.domains.ingestion import service
from app.domains.ingestion.classifier import UnsupportedFileType
from app.domains.ingestion.storage_key import build_storage_key, safe_filename
from app.models.asset import Asset
from app.models.enums import UploadStatus
from app.models.upload import Upload

# ----------------------------------------------------------- 순수 함수


@pytest.mark.parametrize(("filename", "version", "expected"), [
    ("report.pdf", 1, "uploads/7/report_v1.pdf"),
    ("report.pdf", 2, "uploads/7/report_v2.pdf"),
    ("archive.tar.gz", 1, "uploads/7/archive.tar_v1.gz"),   # 마지막 확장자 앞에 붙인다
    ("README", 3, "uploads/7/README_v3"),                    # 확장자 없음
    (".env", 1, "uploads/7/.env_v1"),                        # 점으로 시작하는 이름은 통째로 stem
    ("입찰 데이터.csv", 1, "uploads/7/입찰 데이터_v1.csv"),   # 한글/공백 유지
])
def test_build_storage_key(filename, version, expected):
    assert build_storage_key(7, filename, version) == expected


@pytest.mark.parametrize(("raw", "expected"), [
    ("../../etc/passwd", "passwd"),
    ("C:\\Users\\x\\data.csv", "data.csv"),
    ("a/b/c.pdf", "c.pdf"),
    ("  spaced.csv  ", "spaced.csv"),
])
def test_safe_filename_strips_paths(raw, expected):
    assert safe_filename(raw) == expected


@pytest.mark.parametrize("raw", ["", " ", ".", "..", "a/", "../"])
def test_safe_filename_rejects_invalid(raw):
    with pytest.raises(ValueError, match="invalid filename"):
        safe_filename(raw)


def test_version_must_be_positive():
    with pytest.raises(ValueError, match="version"):
        build_storage_key(1, "a.csv", 0)


def test_key_stays_under_owner_prefix():
    assert build_storage_key(1, "../../x.csv", 1).startswith("uploads/1/")


# ------------------------------------------- upload_file 연결 (가짜 세션/스토리지)


class FakeSession:
    """upload_file이 쓰는 add/commit/refresh/get만 흉내 낸다."""

    def __init__(self):
        self.objects = {}
        self.counters = {}

    def add(self, obj):
        n = self.counters.get(type(obj), 0) + 1
        self.counters[type(obj)] = n
        obj.id = n
        self.objects[(type(obj), n)] = obj

    async def commit(self):
        pass

    async def refresh(self, obj):
        pass

    async def get(self, model, obj_id):
        return self.objects.get((model, obj_id))

    def of(self, model):
        return [o for (t, _), o in self.objects.items() if t is model]


@pytest.fixture
def env(monkeypatch):
    saved: dict[str, bytes] = {}

    def fake_save(key, fileobj):
        saved[key] = fileobj.read()
        return key

    async def fake_count(session, owner_id, filename):
        return sum(1 for u in session.of(Upload) if u.owner_id == owner_id and u.original_filename == filename)

    monkeypatch.setattr(service.storage, "save", fake_save)
    monkeypatch.setattr(service, "count_uploads", fake_count)  # count_uploads의 SQL 자체는 DB가 있어야 검증 가능
    return FakeSession(), saved


async def test_same_filename_does_not_overwrite(env):
    session, saved = env
    first = await service.upload_file(session, 1, "sales.csv", io.BytesIO(b"v1 data"))
    second = await service.upload_file(session, 1, "sales.csv", io.BytesIO(b"v2 data"))

    assert set(saved) == {"uploads/1/sales_v1.csv", "uploads/1/sales_v2.csv"}
    assert saved["uploads/1/sales_v1.csv"] == b"v1 data"  # 첫 원본이 그대로 남아 있다
    assert saved["uploads/1/sales_v2.csv"] == b"v2 data"
    assert first["asset_id"] != second["asset_id"]


async def test_asset_keeps_original_name_and_points_to_versioned_key(env):
    session, _ = env
    await service.upload_file(session, 1, "sales.csv", io.BytesIO(b"x"))
    await service.upload_file(session, 1, "sales.csv", io.BytesIO(b"y"))
    assets = session.of(Asset)

    assert [a.name for a in assets] == ["sales.csv", "sales.csv"]           # 사용자에게 보이는 이름은 그대로
    assert [a.storage_key for a in assets] == ["uploads/1/sales_v1.csv", "uploads/1/sales_v2.csv"]
    assert [u.storage_key for u in session.of(Upload)] == [a.storage_key for a in assets]


async def test_versions_are_per_owner_and_per_filename(env):
    session, saved = env
    await service.upload_file(session, 1, "a.csv", io.BytesIO(b"1"))
    await service.upload_file(session, 2, "a.csv", io.BytesIO(b"2"))   # 다른 사용자
    await service.upload_file(session, 1, "b.csv", io.BytesIO(b"3"))   # 다른 파일명
    assert set(saved) == {"uploads/1/a_v1.csv", "uploads/2/a_v1.csv", "uploads/1/b_v1.csv"}


async def test_failed_classification_still_counts_as_a_version(env):
    """분류에 실패한 파일도 이미 저장돼 있으므로, 같은 이름을 다시 올리면 그 파일을 덮어쓰지 않는다."""
    session, saved = env
    with pytest.raises(UnsupportedFileType):
        await service.upload_file(session, 1, "data.zip", io.BytesIO(b"first"))
    with pytest.raises(UnsupportedFileType):
        await service.upload_file(session, 1, "data.zip", io.BytesIO(b"second"))

    assert set(saved) == {"uploads/1/data_v1.zip", "uploads/1/data_v2.zip"}
    assert [u.status for u in session.of(Upload)] == [UploadStatus.UNSUPPORTED] * 2


async def test_path_in_filename_is_stripped_before_saving(env):
    session, saved = env
    await service.upload_file(session, 1, "../../evil.csv", io.BytesIO(b"x"))
    assert set(saved) == {"uploads/1/evil_v1.csv"}
    assert session.of(Upload)[0].original_filename == "evil.csv"
