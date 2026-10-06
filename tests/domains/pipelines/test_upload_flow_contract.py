"""실제 DB 없이 확인 가능한 부분만: 분류 실패 시에도 예외 타입이 바뀌지 않는지,
그리고 UploadStatus enum에 흐름에 필요한 상태가 다 있는지 정도의 계약 테스트.
DB를 쓰는 전체 흐름(storage 저장 -> uploads insert -> 분류 -> dataset/media_set insert ->
uploads update) 테스트는 testcontainers로 실제 Postgres를 띄워 작성하는 것을 추천."""
from app.domains.ingestion.classifier import UnsupportedFileType
from app.models.enums import UploadStatus


def test_upload_status_has_all_flow_states():
    names = {s.name for s in UploadStatus}
    assert names == {"STORED", "CLASSIFIED", "UNSUPPORTED", "FAILED"}


def test_unsupported_file_type_is_catchable():
    try:
        raise UnsupportedFileType(".zip")
    except UnsupportedFileType as e:
        assert ".zip" in str(e)
