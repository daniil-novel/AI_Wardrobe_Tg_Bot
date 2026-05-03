from uuid import UUID

from aiwardrobe_core.db import get_session
from aiwardrobe_core.security import decode_access_token
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession


async def get_db_session() -> AsyncSession:
    async for session in get_session():
        return session
    raise RuntimeError("Database session was not yielded.")


def get_current_user_id(authorization: str | None = Header(default=None)) -> UUID:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token.")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        return decode_access_token(token)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token.") from exc


CurrentUserId = Depends(get_current_user_id)
DbSession = Depends(get_db_session)
