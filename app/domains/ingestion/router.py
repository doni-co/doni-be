from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.domains.ingestion.classifier import UnsupportedFileType
from app.domains.ingestion.service import upload_file

router = APIRouter(prefix="/uploads", tags=["ingestion"])


@router.post("")
async def upload_route(
    file: UploadFile,
    owner_id: int = 1,  # TODO: 인증 붙으면 현재 로그인 유저로 교체
    session: AsyncSession = Depends(get_session),
):
    try:
        return await upload_file(session, owner_id, file.filename, file.file)
    except UnsupportedFileType as e:
        # 파일은 이미 storage + uploads 테이블에 기록된 상태 (status=unsupported)
        raise HTTPException(400, f"unsupported file type: {e}") from e
