from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.domains.auth.schemas import LoginRequest, TokenResponse
from app.domains.auth.service import login

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login_route(body: LoginRequest, session: AsyncSession = Depends(get_session)):
    token = await login(session, body.email, body.password)
    return TokenResponse(access_token=token)
