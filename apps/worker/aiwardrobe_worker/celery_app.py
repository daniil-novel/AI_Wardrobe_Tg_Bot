from aiwardrobe_core.config import get_settings
from celery import Celery

settings = get_settings()

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
        "aiwardrobe_worker.tasks.research_item": {"queue": "research"},
        "aiwardrobe_worker.tasks.generate_outfit": {"queue": "recommendations"},
        "aiwardrobe_worker.tasks.send_notification": {"queue": "notifications"},
    },
)
