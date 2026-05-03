from datetime import UTC, datetime
from hashlib import sha256
from hmac import new
from urllib.parse import urlencode
from uuid import uuid4

from aiwardrobe_core.config import Settings
from aiwardrobe_core.security import (
    create_access_token,
    decode_access_token,
    validate_telegram_init_data,
)


def signed_init_data(bot_token: str) -> str:
    data = {
        "auth_date": str(int(datetime.now(UTC).timestamp())),
        "query_id": "test-query",
        "user": '{"id":123,"first_name":"Daniil"}',
    }
    data_check = "\n".join(f"{key}={value}" for key, value in sorted(data.items()))
    secret = new(b"WebAppData", bot_token.encode(), sha256).digest()
    data["hash"] = new(secret, data_check.encode(), sha256).hexdigest()
    return urlencode(data)


def test_validate_telegram_init_data() -> None:
    bot_token = "123456:test-token"
    parsed = validate_telegram_init_data(signed_init_data(bot_token), bot_token)
    assert parsed["query_id"] == "test-query"


def test_access_token_roundtrip() -> None:
    settings = Settings(jwt_secret_key="unit-test-secret")
    user_id = uuid4()
    token = create_access_token(user_id, settings)
    assert decode_access_token(token, settings) == user_id
