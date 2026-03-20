from celery import Celery
from celery.schedules import crontab
import os

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/1")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/2")

celery_app = Celery(
    "rag_worker",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=["app.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_max_tasks_per_child=50,
)

# ─── Beat Schedule (Celery Beat periodic tasks) ───────────────────────────────
celery_app.conf.beat_schedule = {
    "archive-warm-sessions": {
        "task": "app.tasks.archive_warm_to_cold",
        "schedule": crontab(hour=3, minute=0),   # Daily at 03:00 UTC
    },
    "cleanup-old-uploads": {
        "task": "app.tasks.cleanup_old_uploads",
        "schedule": crontab(hour=4, minute=0),   # Daily at 04:00 UTC
        "args": (24,),
    },
    "health-check": {
        "task": "app.tasks.health_check",
        "schedule": 300.0,                        # Every 5 minutes
    },
}
