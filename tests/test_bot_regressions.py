from typing import Any

import httpx
import pytest
from aiogram.types import User
from aiwardrobe_bot.keyboards import main_keyboard, result_keyboard
from aiwardrobe_bot.main import register_telegram_upload
from aiwardrobe_core.config import Settings


def test_main_keyboard_points_to_miniapp_url() -> None:
    keyboard = main_keyboard("https://miniapp.example")

    buttons = keyboard.inline_keyboard
    assert buttons[0][0].web_app is not None
    assert buttons[0][0].web_app.url == "https://miniapp.example"
    assert buttons[1][0].callback_data == "upload_help"
    assert buttons[2][0].callback_data == "privacy_policy"


def test_result_keyboard_points_to_miniapp_url() -> None:
    keyboard = result_keyboard("https://miniapp.example/result")

    button = keyboard.inline_keyboard[0][0]
    assert button.web_app is not None
    assert button.web_app.url == "https://miniapp.example/result"


async def test_register_telegram_upload_requires_webhook_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("aiwardrobe_bot.main.get_settings", lambda: Settings(telegram_webhook_secret=""))

    with pytest.raises(RuntimeError, match="TELEGRAM_WEBHOOK_SECRET"):
        await register_telegram_upload(_Message(from_user=User(id=123, is_bot=False, first_name="Daniil")), "file-id")


async def test_register_telegram_upload_requires_user(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "aiwardrobe_bot.main.get_settings",
        lambda: Settings(telegram_webhook_secret="secret", public_api_url="https://api.example"),
    )

    with pytest.raises(RuntimeError, match="Telegram user"):
        await register_telegram_upload(_Message(from_user=None), "file-id")


async def test_register_telegram_upload_posts_private_webhook_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class FakeAsyncClient:
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, *_args: Any) -> None:
            return None

        async def post(self, url: str, **kwargs: Any) -> httpx.Response:
            captured["url"] = url
            captured.update(kwargs)
            request = httpx.Request("POST", url)
            return httpx.Response(200, request=request, json={"id": "upload-123"})

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(
        "aiwardrobe_bot.main.get_settings",
        lambda: Settings(
            telegram_webhook_secret="secret",
            public_api_url="https://public.example",
            internal_api_url="http://api:8000",
        ),
    )

    upload_id = await register_telegram_upload(
        _Message(from_user=User(id=123, is_bot=False, first_name="Daniil", username="dan", language_code="ru")),
        "telegram-file-id",
    )

    assert upload_id == "upload-123"
    assert captured["url"] == "http://api:8000/uploads/from-telegram"
    assert captured["headers"] == {"X-Telegram-Webhook-Secret": "secret"}
    assert captured["json"]["telegram_id"] == 123
    assert captured["json"]["telegram_file_id"] == "telegram-file-id"


class _Message:
    def __init__(self, from_user: User | None) -> None:
        self.from_user = from_user
