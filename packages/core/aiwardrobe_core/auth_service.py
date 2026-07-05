import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aiwardrobe_core.config import Settings
from aiwardrobe_core.models import Session, User
from aiwardrobe_core.security import create_access_token, create_refresh_token, hash_token


@dataclass(frozen=True)
class AuthResult:
    user: User
    access_token: str
    refresh_token: str


def parse_telegram_user(raw_user: str) -> dict[str, Any]:
    parsed = json.loads(raw_user)
    if not isinstance(parsed, dict) or "id" not in parsed:
        raise ValueError("Telegram user payload is invalid.")
    return parsed


async def upsert_telegram_user(session: AsyncSession, telegram_user: dict[str, Any]) -> User:
    telegram_id = int(telegram_user["id"])
    result = await session.execute(select(User).where(User.telegram_id == telegram_id, User.deleted_at.is_(None)))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(telegram_id=telegram_id)
        session.add(user)

    user.telegram_username = telegram_user.get("username")
    user.first_name = telegram_user.get("first_name")
    user.language = telegram_user.get("language_code") or user.language or "ru"
    await session.flush()
    return user


async def issue_session(
    session: AsyncSession,
    user: User,
    settings: Settings,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> AuthResult:
    refresh_token = create_refresh_token()
    auth_session = Session(
        user_id=user.id,
        refresh_token_hash=hash_token(refresh_token),
        user_agent=user_agent,
        ip_hash=hash_token(ip_address) if ip_address else None,
        expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days),
    )
    session.add(auth_session)
    await session.flush()
    access_token = create_access_token(user.id, settings)
    return AuthResult(user=user, access_token=access_token, refresh_token=refresh_token)


async def rotate_refresh_token(session: AsyncSession, refresh_token: str, settings: Settings) -> AuthResult | None:
    token_hash = hash_token(refresh_token)
    result = await session.execute(
        select(Session, User)
        .join(User, User.id == Session.user_id)
        .where(
            Session.refresh_token_hash == token_hash,
            Session.revoked_at.is_(None),
            Session.expires_at > datetime.now(UTC),
            User.deleted_at.is_(None),
        )
    )
    row = result.one_or_none()
    if row is None:
        return None

    auth_session, user = row
    auth_session.revoked_at = datetime.now(UTC)
    return await issue_session(session, user, settings, auth_session.user_agent, None)


async def revoke_refresh_token(session: AsyncSession, refresh_token: str) -> bool:
    result = await session.execute(
        select(Session).where(
            Session.refresh_token_hash == hash_token(refresh_token),
            Session.revoked_at.is_(None),
        )
    )
    auth_session = result.scalar_one_or_none()
    if auth_session is None:
        return False
    auth_session.revoked_at = datetime.now(UTC)
    return True


async def ensure_user_exists(session: AsyncSession, user_id: UUID) -> User | None:
    result = await session.execute(select(User).where(User.id == user_id, User.deleted_at.is_(None)))
    return result.scalar_one_or_none()
