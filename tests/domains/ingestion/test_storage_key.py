"""DB/스토리지 없이 도는 테스트: 저장 키·표시 이름 규칙(순수 함수)과, upload_file이 같은 이름을 덮어쓰지 않는지."""

import hashlib

import pytest

from app.domains.ingestion import service
from app.domains.ingestion.classifier import UnsupportedFileType, guess_content_type
from app.domains.ingestion.parsers import InvalidFileContent
from app.domains.ingestion.storage_key import build_display_name, build_storage_key, safe_filename
from app.models.asset import Asset, AssetRow
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


@pytest.mark.parametrize(("filename", "version", "expected"), [
    ("report.pdf", 1, "report.pdf"),            # 처음에는 그대로
    ("report.pdf", 2, "report (2).pdf"),
    ("report.pdf", 3, "report (3).pdf"),
    ("archive.tar.gz", 2, "archive.tar (2).gz"),
    ("README", 2, "README (2)"),
    ("입찰 데이터.csv", 2, "입찰 데이터 (2).csv"),
])
def test_build_display_name(filename, version, expected):
    assert build_display_name(filename, version) == expected


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
    with pytest.raises(ValueError, match="version"):
        build_display_name("a.csv", 0)


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

    monkeypatch.setattr(service.garage, "save", fake_save)
    monkeypatch.setattr(service.garage, "exists", lambda key: key in saved)
    monkeypatch.setattr(service, "count_uploads", fake_count)  # count_uploads의 SQL 자체는 DB가 있어야 검증 가능
    return FakeSession(), saved


async def test_same_filename_does_not_overwrite(env):
    session, saved = env
    first = await service.upload_file(session, 1, "sales.csv", b"v1 data")
    second = await service.upload_file(session, 1, "sales.csv", b"v2 data")

    assert set(saved) == {"uploads/1/sales_v1.csv", "uploads/1/sales_v2.csv"}
    assert saved["uploads/1/sales_v1.csv"] == b"v1 data"  # 첫 원본이 그대로 남아 있다
    assert saved["uploads/1/sales_v2.csv"] == b"v2 data"
    assert first["asset_id"] != second["asset_id"]


async def test_same_name_and_same_content_are_still_separate_assets(env):
    """이름과 내용이 모두 같아도 합치지 않고 따로 만든다 (같은 데이터를 다르게 정제할 수 있다)."""
    session, saved = env
    first = await service.upload_file(session, 1, "same.csv", b"a,b\n1,2\n")
    second = await service.upload_file(session, 1, "same.csv", b"a,b\n1,2\n")
    assert first["asset_id"] != second["asset_id"]
    assert len(saved) == 2


async def test_asset_display_name_gets_number_but_upload_keeps_original(env):
    session, _ = env
    for _ in range(3):
        await service.upload_file(session, 1, "sales.csv", b"x")

    assert [a.name for a in session.of(Asset)] == ["sales.csv", "sales (2).csv", "sales (3).csv"]
    assert [u.original_filename for u in session.of(Upload)] == ["sales.csv"] * 3
    assert [a.storage_key for a in session.of(Asset)] == [
        "uploads/1/sales_v1.csv", "uploads/1/sales_v2.csv", "uploads/1/sales_v3.csv",
    ]
    assert [u.storage_key for u in session.of(Upload)] == [a.storage_key for a in session.of(Asset)]


async def test_existing_key_is_never_overwritten(env):
    """카운트가 어긋나도(동시 업로드, 옛 데이터) 이미 있는 키는 덮어쓰지 않고 다음 버전으로 저장한다."""
    session, saved = env
    saved["uploads/1/a_v1.csv"] = b"existing"
    saved["uploads/1/a_v2.csv"] = b"existing too"
    await service.upload_file(session, 1, "a.csv", b"new")

    assert saved["uploads/1/a_v1.csv"] == b"existing"
    assert saved["uploads/1/a_v2.csv"] == b"existing too"
    assert saved["uploads/1/a_v3.csv"] == b"new"
    assert session.of(Asset)[0].name == "a (3).csv"  # 표시 번호도 실제 저장된 버전과 같다


async def test_versions_are_per_owner_and_per_filename(env):
    session, saved = env
    await service.upload_file(session, 1, "a.csv", b"1")
    await service.upload_file(session, 2, "a.csv", b"2")   # 다른 사용자
    await service.upload_file(session, 1, "b.csv", b"3")   # 다른 파일명
    assert set(saved) == {"uploads/1/a_v1.csv", "uploads/2/a_v1.csv", "uploads/1/b_v1.csv"}


async def test_failed_classification_still_counts_as_a_version(env):
    """분류에 실패한 파일도 이미 저장돼 있으므로, 같은 이름을 다시 올리면 그 파일을 덮어쓰지 않는다."""
    session, saved = env
    with pytest.raises(UnsupportedFileType):
        await service.upload_file(session, 1, "data.zip", b"first")
    with pytest.raises(UnsupportedFileType):
        await service.upload_file(session, 1, "data.zip", b"second")

    assert set(saved) == {"uploads/1/data_v1.zip", "uploads/1/data_v2.zip"}
    assert [u.status for u in session.of(Upload)] == [UploadStatus.UNSUPPORTED] * 2


async def test_path_in_filename_is_stripped_before_saving(env):
    session, saved = env
    await service.upload_file(session, 1, "../../evil.csv", b"x")
    assert set(saved) == {"uploads/1/evil_v1.csv"}
    assert session.of(Upload)[0].original_filename == "evil.csv"


# ------------------------------------------- 메타데이터 · 정형 파일 행 적재 · 파싱 실패


async def test_csv_upload_stores_rows_and_metadata(env):
    session, saved = env
    data = "이름,금액\n홍길동,100\n,200\n".encode()
    result = await service.upload_file(session, 1, "sales.csv", data)

    asset = session.of(Asset)[0]
    assert result["kind"] == "dataset"
    assert asset.row_count == 2
    assert asset.schema_def == {"columns": ["이름", "금액"]}
    rows = session.of(AssetRow)
    assert [r.row_idx for r in rows] == [0, 1]
    assert [r.data for r in rows] == [{"이름": "홍길동", "금액": "100"}, {"이름": None, "금액": "200"}]
    assert saved["uploads/1/sales_v1.csv"] == data  # 원본은 그대로 Garage에 있다


async def test_metadata_size_sha256_and_content_type(env):
    session, _ = env
    data = b"a,b\n1,2\n"
    await service.upload_file(session, 1, "sales.csv", data)
    asset = session.of(Asset)[0]
    assert asset.size_bytes == len(data)
    assert asset.sha256 == hashlib.sha256(data).hexdigest()
    assert asset.content_type == "text/csv"  # 확장자로 추정


async def test_content_type_from_client_wins(env):
    session, _ = env
    await service.upload_file(session, 1, "sales.csv", b"a\n1\n", "application/vnd.ms-excel")
    assert session.of(Asset)[0].content_type == "application/vnd.ms-excel"


@pytest.mark.parametrize(("filename", "expected"), [
    ("a.csv", "text/csv"),
    ("a.CSV", "text/csv"),
    ("a.pdf", "application/pdf"),
    ("a.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    ("a.hwp", "application/x-hwp"),
    ("a.unknown", "application/octet-stream"),
    ("noext", "application/octet-stream"),
])
def test_guess_content_type(filename, expected):
    assert guess_content_type(filename) == expected  # OS(mimetypes)와 무관하게 항상 같다


async def test_generic_octet_stream_falls_back_to_extension(env):
    """브라우저·curl이 종류를 모를 때 보내는 octet-stream은 확장자로 다시 정한다."""
    session, _ = env
    await service.upload_file(session, 1, "sales.csv", b"a,b", "application/octet-stream")
    assert session.of(Asset)[0].content_type == "text/csv"


async def test_same_content_is_not_merged(env):
    """sha256이 같아도 합치지 않는다 (같은 데이터를 다르게 정제할 수 있다)."""
    session, _ = env
    await service.upload_file(session, 1, "a.csv", b"x\n1\n")
    await service.upload_file(session, 1, "b.csv", b"x\n1\n")
    assets = session.of(Asset)
    assert len(assets) == 2
    assert assets[0].sha256 == assets[1].sha256
    assert assets[0].id != assets[1].id
    assert len(session.of(AssetRow)) == 2  # 행도 각각 저장


async def test_broken_csv_keeps_original_and_marks_invalid(env):
    session, saved = env
    with pytest.raises(InvalidFileContent, match="row 2"):
        await service.upload_file(session, 1, "bad.csv", b"a,b\n1,2,3\n")

    assert saved["uploads/1/bad_v1.csv"] == b"a,b\n1,2,3\n"  # 원본은 남는다
    assert session.of(Asset) == []
    assert session.of(AssetRow) == []
    upload = session.of(Upload)[0]
    assert upload.status == UploadStatus.INVALID
    assert "row 2" in upload.error


async def test_retry_after_invalid_gets_next_version(env):
    session, saved = env
    with pytest.raises(InvalidFileContent):
        await service.upload_file(session, 1, "bad.csv", b"a,b\n1,2,3\n")
    await service.upload_file(session, 1, "bad.csv", b"a,b\n1,2\n")
    assert set(saved) == {"uploads/1/bad_v1.csv", "uploads/1/bad_v2.csv"}
    assert session.of(Asset)[0].name == "bad (2).csv"


async def test_mediaset_has_no_rows(env):
    session, saved = env
    result = await service.upload_file(session, 1, "report.pdf", b"%PDF-1.4")
    asset = session.of(Asset)[0]
    assert result["kind"] == "mediaset"
    assert asset.row_count is None and asset.schema_def is None
    assert session.of(AssetRow) == []
    assert asset.size_bytes == 8
    assert "uploads/1/report_v1.pdf" in saved


async def test_xls_is_accepted_as_mediaset(env):
    session, _ = env
    result = await service.upload_file(session, 1, "old.xls", b"\xd0\xcf\x11\xe0")
    assert result["kind"] == "mediaset"


async def test_json_upload_stores_rows(env):
    session, _ = env
    await service.upload_file(session, 1, "data.json", b'[{"a":1},{"a":2,"b":{"x":1}}]')
    asset = session.of(Asset)[0]
    assert asset.schema_def == {"columns": ["a", "b"]}
    assert [r.data for r in session.of(AssetRow)] == [{"a": 1, "b": None}, {"a": 2, "b": {"x": 1}}]
