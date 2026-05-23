from uuid import uuid4

from aiwardrobe_core.logging import hash_identifier, redact_mapping, redact_value
from aiwardrobe_core.security import create_access_token


def test_redact_mapping_removes_secret_like_fields_and_values() -> None:
    payload = {
        "authorization": "Bearer secret-token",
        "nested": {"openrouter_api_key": "sk-or-v1-this-should-not-leak"},
        "message": "token sk-or-v1-this-should-not-leak",
        "safe": "wardrobe",
    }

    redacted = redact_mapping(payload)

    assert redacted["authorization"] == "[REDACTED]"
    assert redacted["nested"]["openrouter_api_key"] == "[REDACTED]"
    assert redacted["message"] == "token [REDACTED]"
    assert redacted["safe"] == "wardrobe"


def test_redact_value_handles_lists() -> None:
    assert redact_value(["sk-or-v1-this-should-not-leak", "ok"]) == ["[REDACTED]", "ok"]


def test_hash_identifier_is_stable_and_does_not_expose_raw_id() -> None:
    raw = str(uuid4())

    hashed = hash_identifier(raw)

    assert hashed == hash_identifier(raw)
    assert raw not in hashed
    assert len(hashed) == 16


def test_request_logging_user_hash_can_decode_access_token() -> None:
    from aiwardrobe_api.logging_middleware import RequestLoggingMiddleware
    from fastapi import Request

    user_id = uuid4()
    token = create_access_token(user_id)
    scope = {"type": "http", "headers": [(b"authorization", f"Bearer {token}".encode())]}

    assert RequestLoggingMiddleware._user_hash(Request(scope)) == hash_identifier(str(user_id))
