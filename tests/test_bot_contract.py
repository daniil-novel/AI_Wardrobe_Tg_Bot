from pathlib import Path


def test_bot_photo_flow_registers_upload_with_backend() -> None:
    bot_file = Path("apps/bot/aiwardrobe_bot/main.py").read_text(encoding="utf-8")

    assert "httpx.AsyncClient" in bot_file
    assert "/uploads/from-telegram" in bot_file
    assert "internal_api_url" in bot_file
    assert "TELEGRAM_BOT_TOKEN is required" in bot_file
