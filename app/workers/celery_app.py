from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "simulate-telemetry-every-5-seconds": {
            "task": "app.workers.tasks.simulate_telemetry_task",
            "schedule": 5.0,
        },
    },
)

celery_app.autodiscover_tasks(["app.workers"])
