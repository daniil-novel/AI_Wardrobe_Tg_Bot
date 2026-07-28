from typing import Any

from aiwardrobe_core.config import get_settings
from aiwardrobe_core.logging import configure_logging
from celery import Celery
from celery.signals import setup_logging

settings = get_settings()
configure_logging(settings.log_level, settings.log_file_for("worker"))


@setup_logging.connect
def _configure_worker_logging(**_kwargs: Any) -> None:
    # Keep our root handlers (stdout + rotating file) instead of Celery's own setup.
    configure_logging(settings.log_level, settings.log_file_for("worker"))


celery_app = Celery(
    "aiwardrobe_worker",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["aiwardrobe_worker.tasks"],
)

celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_default_retry_delay=30,
    task_routes={
        "aiwardrobe_worker.tasks.analyze_upload": {"queue": "ai"},
        "aiwardrobe_worker.tasks.transfer_telegram_upload": {"queue": "ai"},
        "aiwardrobe_worker.tasks.research_item": {"queue": "research"},
        "aiwardrobe_worker.tasks.generate_outfit": {"queue": "recommendations"},
        "aiwardrobe_worker.tasks.send_notification": {"queue": "notifications"},
    },
)
