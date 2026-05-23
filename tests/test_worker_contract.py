from pathlib import Path
from uuid import uuid4

import pytest
from aiwardrobe_core.config import Settings
from aiwardrobe_worker.tasks import analyze_upload, generate_outfit, research_item, send_notification


def test_worker_tasks_do_not_return_placeholder_provider_statuses() -> None:
    worker_file = Path("apps/worker/aiwardrobe_worker/tasks.py").read_text(encoding="utf-8")

    assert "pending_provider_integration" not in worker_file
    assert "generate_text_json" in worker_file
    assert "OutfitCard" in worker_file


def test_ai_worker_tasks_fail_closed_without_openrouter_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("aiwardrobe_worker.tasks.get_settings", lambda: Settings(openrouter_api_key=""))

    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        analyze_upload.run(str(uuid4()), "https://signed.example/image.jpg")
    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        research_item.run(str(uuid4()), "blue cotton shirt")
    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        generate_outfit.run(str(uuid4()), {"event_type": "office"})


def test_research_task_rejects_empty_private_description() -> None:
    with pytest.raises(ValueError, match="text description"):
        research_item.run(str(uuid4()), "")


def test_notification_task_fails_closed_without_bot_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("aiwardrobe_worker.tasks.get_settings", lambda: Settings(telegram_bot_token=""))

    with pytest.raises(RuntimeError, match="TELEGRAM_BOT_TOKEN"):
        send_notification.run(123456, "Done")
