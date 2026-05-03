import json
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status

from aiwardrobe_core.config import get_settings
from aiwardrobe_core.schemas import TelegramAuthRequest, TokenPair
from aiwardrobe_core.security import TelegramAuthError, create_access_token, validate_telegram_init_data

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/telegram", response_model=TokenPair)
async def telegram_auth(payload: TelegramAuthRequest) -> TokenPair:
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
    telegram_user = json.loads(user_raw)
    stable_user_uuid = uuid4()
    # Persistence is intentionally handled by the users service in the next iteration.
    # The contract returns a real signed JWT and never trusts client-side user fields.
    access_token = create_access_token(stable_user_uuid, settings)
    return TokenPair(access_token=access_token)


@router.post("/refresh", response_model=TokenPair)
async def refresh() -> TokenPair:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Refresh sessions are scaffolded.")


@router.post("/logout")
async def logout() -> dict[str, str]:
    return {"status": "logged_out"}
