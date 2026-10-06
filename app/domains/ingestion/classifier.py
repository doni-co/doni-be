"""순수 함수: 파일 확장자로 dataset/media_set을 구분한다. DB, 네트워크에 의존하지 않는다."""
from pathlib import Path

from app.models.enums import AssetKind

DATASET_EXT = {".csv", ".tsv", ".parquet", ".json"}
MEDIA_EXT = {".pdf", ".ppt", ".pptx", ".hwp", ".hwpx", ".png", ".jpg", ".jpeg", ".docx", ".xlsx"}


class UnsupportedFileType(Exception):
    pass


def classify_by_extension(filename: str) -> AssetKind:
    ext = Path(filename).suffix.lower()
    if ext in DATASET_EXT:
        return AssetKind.DATASET
    if ext in MEDIA_EXT:
        return AssetKind.MEDIA_SET
    raise UnsupportedFileType(ext)
