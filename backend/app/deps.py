import uuid

from fastapi import Cookie, Depends, HTTPException, status
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from moneyman_shared.config import get_settings
from moneyman_shared.db.models.user import User
from moneyman_shared.db.session import get_db

settings = get_settings()

JWT_ALGORITHM = "HS256"


def create_session_token(user_id: uuid.UUID) -> str:
    return jwt.encode({"sub": str(user_id)}, settings.SESSION_SECRET, algorithm=JWT_ALGORITHM)


def decode_session_token(token: str) -> uuid.UUID:
    try:
        payload = jwt.decode(token, settings.SESSION_SECRET, algorithms=[JWT_ALGORITHM])
        return uuid.UUID(payload["sub"])
    except (JWTError, KeyError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session") from exc


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    session_token: str | None = Cookie(default=None, alias=settings.SESSION_COOKIE_NAME),
) -> User:
    if session_token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    user_id = decode_session_token(session_token)

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return user
