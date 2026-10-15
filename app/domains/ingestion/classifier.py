"""순수 함수: 파일 확장자로 dataset/media_set을 구분한다. DB, 네트워크에 의존하지 않는다."""
from pathlib import Path

from app.models.enums import AssetKind

DATASET_EXT = {".csv", ".tsv", ".parquet", ".json"}
MEDIA_EXT = {".pdf", ".ppt", ".pptx", ".hwp", ".hwpx", ".png", ".jpg", ".jpeg", ".docx", ".xlsx", ".xls", ".txt"}


# 클라이언트가 content-type을 안 주면 확장자로 정한다. OS별 mimetypes 차이(Windows 레지스트리 등)를 피하려고 직접 둔다.
_CONTENT_TYPES = {
    ".csv": "text/csv",
    ".tsv": "text/tab-separated-values",
    ".json": "application/json",
    ".parquet": "application/vnd.apache.parquet",
    ".txt": "text/plain",
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".ppt": "application/vnd.ms-powerpoint",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".hwp": "application/x-hwp",
    ".hwpx": "application/x-hwpx",
}


class UnsupportedFileType(Exception):
    pass


def guess_content_type(filename: str) -> str:
    return _CONTENT_TYPES.get(Path(filename).suffix.lower(), "application/octet-stream")


def classify_by_extension(filename: str) -> AssetKind:
    ext = Path(filename).suffix.lower()
    if ext in DATASET_EXT:
        return AssetKind.DATASET
    if ext in MEDIA_EXT:
        return AssetKind.MEDIASET
    raise UnsupportedFileType(ext)
