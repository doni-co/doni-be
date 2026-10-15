from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.domains.ingestion.classifier import UnsupportedFileType
from app.domains.ingestion.parsers import InvalidFileContent
from app.domains.ingestion.service import upload_file
from app.domains.ingestion.storage_key import safe_filename

router = APIRouter(prefix="/uploads", tags=["ingestion"])

MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # 100MB (프론트 업로드 창 안내와 같다)


@router.post("")
async def upload_route(
    file: UploadFile,
    owner_id: int = 1,  # TODO: 인증 붙으면 현재 로그인 유저로 교체
    session: AsyncSession = Depends(get_session),
):
    try:
        filename = safe_filename(file.filename or "")
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "file too large (max 100MB)")
    try:
        return await upload_file(session, owner_id, filename, data, file.content_type)
    except UnsupportedFileType as e:
        # 파일은 이미 storage + uploads 테이블에 기록된 상태 (status=unsupported)
        raise HTTPException(400, f"unsupported file type: {e}") from e
    except InvalidFileContent as e:
        # 원본은 저장되고 uploads에 status=invalid로 남는다
        raise HTTPException(400, f"invalid file content: {e}") from e
