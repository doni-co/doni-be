"""presigned URL은 서명에 호스트가 들어간다. 외부(AI 서버 등)용 주소가 따로 있으면 그 주소로 서명해야 한다.
boto3의 URL 서명은 네트워크 없이 이뤄진다."""
import pytest

from app.core.config import settings
from app.infrastructure.storage import garage


@pytest.fixture(autouse=True)
def fresh_garage(monkeypatch):
    monkeypatch.setattr(settings, "garage_access_key", "test-access-key")
    monkeypatch.setattr(settings, "garage_secret_key", "test-secret-key")
    monkeypatch.setattr(settings, "garage_bucket", "doni")
    monkeypatch.setattr(settings, "garage_endpoint_url", "http://garage:3900")
    monkeypatch.setattr(garage, "_client", None)
    monkeypatch.setattr(garage, "_presign_client", None)


def test_presigned_url_uses_public_url_when_set(monkeypatch):
    monkeypatch.setattr(settings, "garage_public_url", "http://files.example.test:3900")
    url = garage.presigned_url("uploads/1/a_v1.pdf")
    assert url.startswith("http://files.example.test:3900/doni/uploads/1/a_v1.pdf?")
    assert "X-Amz-Signature=" in url


def test_presigned_url_falls_back_to_endpoint(monkeypatch):
    monkeypatch.setattr(settings, "garage_public_url", "")
    url = garage.presigned_url("uploads/1/a_v1.pdf")
    assert url.startswith("http://garage:3900/doni/uploads/1/a_v1.pdf?")


def test_internal_client_is_unchanged_by_public_url(monkeypatch):
    monkeypatch.setattr(settings, "garage_public_url", "http://files.example.test:3900")
    assert garage._get_client().meta.endpoint_url == "http://garage:3900"
    assert garage._get_presign_client().meta.endpoint_url == "http://files.example.test:3900"


def test_path_style_addressing(monkeypatch):
    monkeypatch.setattr(settings, "garage_public_url", "")
    assert garage._get_client().meta.config.s3["addressing_style"] == "path"
