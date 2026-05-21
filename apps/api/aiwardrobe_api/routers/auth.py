from aiwardrobe_core.auth_service import (
    issue_session,
    parse_telegram_user,
    revoke_refresh_token,
    rotate_refresh_token,
    upsert_telegram_user,
)
from aiwardrobe_core.config import get_settings
from aiwardrobe_core.schemas import LogoutRequest, RefreshTokenRequest, TelegramAuthRequest, TokenPair
from aiwardrobe_core.security import (
    TelegramAuthError,
    validate_telegram_init_data,
)
from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from aiwardrobe_api.dependencies import DbSession

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/telegram", response_model=TokenPair)
async def telegram_auth(payload: TelegramAuthRequest, request: Request, session: AsyncSession = DbSession) -> TokenPair:
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="TELEGRAM_BOT_TOKEN is required for real Telegram auth.",
        )
    try:
        parsed = validate_telegram_init_data(payload.init_data, settings.telegram_bot_token)
    except TelegramAuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    user_raw = parsed.get("user")
    if not user_raw:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Telegram user is missing.")
    try:
        telegram_user = parse_telegram_user(user_raw)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    user = await upsert_telegram_user(session, telegram_user)
    auth = await issue_session(
        session,
        user,
        settings,
        request.headers.get("user-agent"),
        request.client.host if request.client else None,
    )
    await session.commit()
    return TokenPair(access_token=auth.access_token, refresh_token=auth.refresh_token)


@router.post("/refresh", response_model=TokenPair)
async def refresh(payload: RefreshTokenRequest, session: AsyncSession = DbSession) -> TokenPair:
    settings = get_settings()
    auth = await rotate_refresh_token(session, payload.refresh_token, settings)
    if auth is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token is invalid or expired.")
    await session.commit()
    return TokenPair(access_token=auth.access_token, refresh_token=auth.refresh_token)


@router.post("/logout")
async def logout(payload: LogoutRequest, session: AsyncSession = DbSession) -> dict[str, str]:
    await revoke_refresh_token(session, payload.refresh_token)
    await session.commit()
    return {"status": "logged_out"}
