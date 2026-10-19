"""원천/결과 파일을 Garage(S3 호환)에 저장/조회하는 경계.
도메인 코드는 이 함수들을 통해서만 파일에 접근한다 (엔드포인트를 직접 다루지 않는다).
나중에 다른 S3 호환 스토리지로 바꿔도 이 모듈의 함수 시그니처만 유지하면 호출부는 그대로 둘 수 있다."""
from typing import BinaryIO

import boto3
from botocore.config import Config

from app.core.config import settings

_client = None
_presign_client = None


def _new_client(endpoint_url: str):
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        region_name=settings.garage_region,
        aws_access_key_id=settings.garage_access_key,
        aws_secret_access_key=settings.garage_secret_key,
        config=Config(
            s3={"addressing_style": "path"},  # http://garage:3900/버킷/키 형태로 요청
            request_checksum_calculation="when_required",  # boto3 1.36+ 기본 체크섬 헤더를 S3 호환 서버에 강제하지 않음
            response_checksum_validation="when_required",
        ),
    )


def _get_client():
    global _client
    if _client is None:
        _client = _new_client(settings.garage_endpoint_url)
    return _client


def _get_presign_client():
    """presigned URL은 서명에 호스트가 들어가므로, 외부 주소가 따로 있으면 그 주소로 서명한다."""
    global _presign_client
    if not settings.garage_public_url:
        return _get_client()
    if _presign_client is None:
        _presign_client = _new_client(settings.garage_public_url)
    return _presign_client


def save(key, fileobj):
    _get_client().upload_fileobj(fileobj, settings.garage_bucket, key)
    return key


def open_file(key: str) -> BinaryIO:
    obj = _get_client().get_object(Bucket=settings.garage_bucket, Key=key)
    return obj["Body"]  # botocore StreamingBody, BinaryIO처럼 .read() 가능


def exists(key: str) -> bool:
    try:
        _get_client().head_object(Bucket=settings.garage_bucket, Key=key)
        return True
    except _get_client().exceptions.ClientError:
        return False


def presigned_url(key: str, expires_in: int = 3600) -> str:
    """AI 서버 등 외부로 원본 위치를 직접 넘겨줄 때 사용 (바이트를 직접 안 보내도 되게)."""
    return _get_presign_client().generate_presigned_url(
        "get_object", Params={"Bucket": settings.garage_bucket, "Key": key}, ExpiresIn=expires_in
    )
