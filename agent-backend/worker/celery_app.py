from celery import Celery
from dotenv import load_dotenv
import os

load_dotenv()

celery_app = Celery(
    "pi_analysis",
    broker=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=int(os.environ.get("PI_TIMEOUT_SECONDS", 5400)) + 60,
)

celery_app.conf.beat_schedule = {
    "cleanup-workspaces-every-hour": {
        "task": "worker.cleanup.cleanup_expired_workspaces",
        "schedule": 3600.0,
    },
}

celery_app.conf.imports = ["worker.tasks", "worker.cleanup"]