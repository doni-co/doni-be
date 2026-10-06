import pytest

from app.domains.ingestion.classifier import UnsupportedFileType, classify_by_extension
from app.models.enums import AssetKind


def test_dataset_extension():
    assert classify_by_extension("sales.csv") is AssetKind.DATASET


def test_media_extension():
    assert classify_by_extension("report.pdf") is AssetKind.MEDIA_SET


def test_unsupported_extension():
    with pytest.raises(UnsupportedFileType):
        classify_by_extension("archive.zip")
