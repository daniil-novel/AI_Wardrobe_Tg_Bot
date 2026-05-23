from pathlib import Path


def test_worker_tasks_do_not_return_placeholder_provider_statuses() -> None:
    worker_file = Path("apps/worker/aiwardrobe_worker/tasks.py").read_text(encoding="utf-8")

    assert "pending_provider_integration" not in worker_file
    assert "generate_text_json" in worker_file
    assert "OutfitCard" in worker_file
