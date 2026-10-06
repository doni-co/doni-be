import jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def login(session: AsyncSession, email: str, password: str) -> str:
    user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None or not _pwd.verify(password, user.password_hash):
        raise ValueError("invalid credentials")
    return jwt.encode({"sub": str(user.id)}, settings.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> int:
    payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    return int(payload["sub"])
