"""원천/결과 파일을 Garage(S3 호환)에 저장/조회하는 경계.
도메인 코드는 이 함수들을 통해서만 파일에 접근한다 (엔드포인트를 직접 다루지 않는다).
나중에 다른 S3 호환 스토리지로 바꿔도 이 모듈의 함수 시그니처만 유지하면 호출부는 그대로 둘 수 있다."""
from typing import BinaryIO

import boto3

from app.core.config import settings

_client = boto3.client(
    "s3",
    endpoint_url=settings.garage_endpoint_url,
    region_name=settings.garage_region,
    aws_access_key_id=settings.garage_access_key,
    aws_secret_access_key=settings.garage_secret_key,
)


def save(key: str, fileobj: BinaryIO) -> str:
    _client.upload_fileobj(fileobj, settings.garage_bucket, key)
    return key


def open_file(key: str) -> BinaryIO:
    obj = _client.get_object(Bucket=settings.garage_bucket, Key=key)
    return obj["Body"]  # botocore StreamingBody, BinaryIO처럼 .read() 가능


def exists(key: str) -> bool:
    try:
        _client.head_object(Bucket=settings.garage_bucket, Key=key)
        return True
    except _client.exceptions.ClientError:
        return False


def presigned_url(key: str, expires_in: int = 3600) -> str:
    """AI 서버 등 외부로 원본 위치를 직접 넘겨줄 때 사용 (바이트를 직접 안 보내도 되게)."""
    return _client.generate_presigned_url(
        "get_object", Params={"Bucket": settings.garage_bucket, "Key": key}, ExpiresIn=expires_in
    )
