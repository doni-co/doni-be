import asyncio
import hashlib
import io

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.assets.service import register_asset, save_rows
from app.domains.ingestion.classifier import (
    UnsupportedFileType,
    classify_by_extension,
    guess_content_type,
)
from app.domains.ingestion.parsers import PARSEABLE_EXT, InvalidFileContent, parse_tabular
from app.domains.ingestion.storage_key import build_display_name, build_storage_key, safe_filename
from app.infrastructure.storage import garage
from app.models.enums import AssetKind, UploadStatus
from app.models.upload import Upload

# uploads 테이블 쿼리 함수. ingestion이 소유하는 테이블이고 upload_file과 한 세트로만 쓰이므로
# 별도 파일로 나누지 않고 여기 둔다 (pipelines 쪽과 동일한 기준: 쿼리 + 오케스트레이션을 한 파일에).


async def register_upload(session: AsyncSession, owner_id: int, filename: str, storage_key: str) -> Upload:
    """storage.save 직후 호출. 분류 전 상태(STORED)로 먼저 기록을 남긴다."""
    upload = Upload(
        owner_id=owner_id,
        original_filename=filename,
        storage_key=storage_key,
        status=UploadStatus.STORED,
    )
    session.add(upload)
    await session.commit()
    await session.refresh(upload)
    return upload


async def mark_classified(session: AsyncSession, upload_id: int, asset_kind: AssetKind, asset_id: int) -> Upload:
    upload = await session.get(Upload, upload_id)
    upload.status = UploadStatus.CLASSIFIED
    upload.asset_kind = asset_kind
    upload.asset_id = asset_id
    await session.commit()
    return upload


async def mark_failed(session: AsyncSession, upload_id: int, status: UploadStatus, error: str) -> Upload:
    upload = await session.get(Upload, upload_id)
    upload.status = status
    upload.error = error
    await session.commit()
    return upload


async def count_uploads(session: AsyncSession, owner_id: int, filename: str) -> int:
    """같은 사용자가 같은 이름으로 올린 기록 수. 분류에 실패한 업로드도 파일은 이미 저장돼 있으므로 센다."""
    result = await session.execute(
        select(func.count()).select_from(Upload).where(
            Upload.owner_id == owner_id, Upload.original_filename == filename
        )
    )
    return result.scalar_one()


async def upload_file(
    session: AsyncSession, owner_id: int, filename: str, data: bytes, content_type: str | None = None
) -> dict:
    filename = safe_filename(filename)
    version = await count_uploads(session, owner_id, filename) + 1       # 같은 이름이면 2, 3 ... (파일은 절대 갱신하지 않는다)
    key = build_storage_key(owner_id, filename, version)
    while await asyncio.to_thread(garage.exists, key):                   # 이미 있는 키는 덮어쓰지 않고 다음 버전으로 (동시 업로드 방어)
        version += 1
        key = build_storage_key(owner_id, filename, version)

    size_bytes = len(data)                                               # 원본 메타데이터 (무결성 확인용, 중복 제거에는 쓰지 않는다)
    sha256 = hashlib.sha256(data).hexdigest()
    if not content_type or content_type == "application/octet-stream":   # 클라이언트가 종류를 모르면 확장자로 정한다
        content_type = guess_content_type(filename)

    await asyncio.to_thread(garage.save, key, io.BytesIO(data))          # ① 원본 바이트 저장 (Garage). boto3는 동기라 스레드에서 실행

    upload = await register_upload(session, owner_id, filename, key)     # ② 공통 업로드 기록 (분류 전에 바로 남김). 원래 파일명을 그대로 기록

    try:
        kind = classify_by_extension(filename)                          # ③ 분류
    except UnsupportedFileType as e:
        await mark_failed(session, upload.id, UploadStatus.UNSUPPORTED, str(e))
        raise

    ext = filename.rsplit(".", 1)[-1] if "." in filename else ""
    parsed = None
    if kind is AssetKind.DATASET and ext.lower() in PARSEABLE_EXT:      # 정형 파일은 행까지 읽어 둔다 (파이프라인 첫 노드의 입력)
        try:
            parsed = parse_tabular(data, ext)
        except InvalidFileContent as e:
            await mark_failed(session, upload.id, UploadStatus.INVALID, str(e))  # 원본은 이미 저장돼 남는다
            raise

    asset = await register_asset(                                         # ④ Asset 등록 (메타데이터 DB 저장). 같은 이름이면 "name (2).csv"
        session, owner_id=owner_id, name=build_display_name(filename, version), kind=kind, storage_key=key, ext=ext,
        size_bytes=size_bytes, content_type=content_type, sha256=sha256,
    )
    if parsed is not None:
        columns, rows = parsed
        await save_rows(session, asset.id, columns, rows)                # 행은 한 번만 저장된다 (assets.service.save_rows 가드)

    await mark_classified(session, upload.id, kind, asset.id)            # ⑤ 업로드 기록에 분류 결과 연결

    return {"upload_id": upload.id, "asset_id": asset.id, "kind": kind.value}
