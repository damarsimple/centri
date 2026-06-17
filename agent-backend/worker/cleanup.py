import os
import time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from worker.celery_app import celery_app
from app.workspace import delete_workspace
from app.job_store import delete_job


@celery_app.task
def cleanup_expired_workspaces():
    workspace_dir = Path(os.environ.get("WORKSPACE_DIR", "./workspaces"))
    ttl_hours = int(os.environ.get("WORKSPACE_TTL_HOURS", 24))
    now = time.time()
    ttl_seconds = ttl_hours * 3600

    if not workspace_dir.exists():
        return

    for item in workspace_dir.iterdir():
        if not item.is_dir() or not item.name.startswith("job_"):
            continue
        mtime = item.stat().st_mtime
        if now - mtime > ttl_seconds:
            job_id = item.name.replace("job_", "")
            delete_workspace(job_id)
            delete_job(job_id)