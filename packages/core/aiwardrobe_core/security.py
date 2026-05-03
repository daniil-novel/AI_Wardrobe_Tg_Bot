from datetime import UTC, datetime, timedelta
from hashlib import sha256
from hmac import compare_digest, new
from typing import cast
from urllib.parse import parse_qsl
from uuid import UUID

import jwt

from aiwardrobe_core.config import Settings, get_settings


class TelegramAuthError(ValueError):
    pass


def validate_telegram_init_data(init_data: str, bot_token: str, max_age_seconds: int = 86400) -> dict[str, str]:
    parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        raise TelegramAuthError("Telegram initData hash is missing.")

    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(parsed.items()))
    secret_key = new(b"WebAppData", bot_token.encode(), sha256).digest()
    expected_hash = new(secret_key, data_check_string.encode(), sha256).hexdigest()
    if not compare_digest(expected_hash, received_hash):
        raise TelegramAuthError("Telegram initData hash is invalid.")

    auth_date_raw = parsed.get("auth_date")
    if auth_date_raw is None:
        raise TelegramAuthError("Telegram initData auth_date is missing.")
    auth_date = datetime.fromtimestamp(int(auth_date_raw), tz=UTC)
    if datetime.now(UTC) - auth_date > timedelta(seconds=max_age_seconds):
        raise TelegramAuthError("Telegram initData is expired.")
    return parsed


def create_access_token(user_id: UUID, settings: Settings | None = None) -> str:
    resolved = settings or get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=resolved.access_token_expire_minutes)).timestamp()),
    }
    return cast(str, jwt.encode(payload, resolved.jwt_secret_key, algorithm=resolved.jwt_algorithm))


def decode_access_token(token: str, settings: Settings | None = None) -> UUID:
    resolved = settings or get_settings()
    payload = jwt.decode(token, resolved.jwt_secret_key, algorithms=[resolved.jwt_algorithm])
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Token is not an access token.")
    return UUID(str(payload["sub"]))
