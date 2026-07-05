from collections.abc import AsyncIterator
from uuid import UUID

from aiwardrobe_core.auth_service import ensure_user_exists
from aiwardrobe_core.db import get_session_factory
from aiwardrobe_core.security import decode_access_token
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Yield-style dependency so FastAPI closes the session and returns the connection to the pool.

    Returning the session out of the generator (the previous implementation) leaked one pooled
    connection per request until GC, which exhausted the pool under normal Mini App traffic.
    """
    async with get_session_factory()() as session:
        yield session


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


async def get_current_user(user_id: UUID = CurrentUserId, session: AsyncSession = DbSession) -> UUID:
    if await ensure_user_exists(session, user_id) is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User does not exist.")
    return user_id


CurrentUser = Depends(get_current_user)
