from typing import BinaryIO

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import storage
from app.domains.assets.service import register_asset
from app.domains.ingestion.classifier import UnsupportedFileType, classify_by_extension
from app.models.enums import AssetKind, UploadStatus
from app.models.upload import Upload

# uploads 테이블 쿼리 함수. ingestion이 소유하는 테이블이고 upload_file과 한 세트로만 쓰이므로
# 별도 파일로 나누지 않고 여기 둔다 (pipelines/service.py와 동일한 기준: 쿼리 + 오케스트레이션을 한 파일에).


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


async def upload_file(session: AsyncSession, owner_id: int, filename: str, fileobj: BinaryIO) -> dict:
    key = f"uploads/{owner_id}/{filename}"
    storage.save(key, fileobj)                                           # ① 파일 바이트 저장

    upload = await register_upload(session, owner_id, filename, key)     # ② 공통 업로드 기록 (분류 전에 바로 남김)

    try:
        kind = classify_by_extension(filename)                          # ③ 분류
    except UnsupportedFileType as e:
        await mark_failed(session, upload.id, UploadStatus.UNSUPPORTED, str(e))
        raise

    ext = filename.rsplit(".", 1)[-1] if "." in filename else ""
    asset = await register_asset(                                         # ④ Asset 등록 (메타데이터 DB 저장)
        session, owner_id=owner_id, name=filename, kind=kind, storage_key=key, ext=ext,
    )

    await mark_classified(session, upload.id, kind, asset.id)            # ⑤ 업로드 기록에 분류 결과 연결

    return {"upload_id": upload.id, "asset_id": asset.id, "kind": kind.value}
