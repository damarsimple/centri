import redis
import json
import os
import time
from typing import Optional, Dict, Any

redis_client = redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))

STATE_TTL = int(os.environ.get("JOB_STATE_TTL", str(48 * 60 * 60)))
RESULT_TTL = int(os.environ.get("JOB_RESULT_TTL", str(48 * 60 * 60)))


def _state_key(job_id: str) -> str:
    return f"job:{job_id}:state"


def _result_key(job_id: str) -> str:
    return f"job:{job_id}:result"


def set_state(job_id: str, **kwargs) -> None:
    key = _state_key(job_id)
    existing = redis_client.get(key)
    if existing:
        state = json.loads(existing)
    else:
        state = {}
    state.update(kwargs)
    redis_client.setex(key, STATE_TTL, json.dumps(state))


def get_state(job_id: str) -> Optional[Dict[str, Any]]:
    key = _state_key(job_id)
    data = redis_client.get(key)
    if data:
        return json.loads(data)
    return None


def set_result(job_id: str, stats: Dict[str, Any], files: Dict[str, str]) -> None:
    key = _result_key(job_id)
    result = {"stats": stats, "files": files}
    redis_client.setex(key, RESULT_TTL, json.dumps(result))


def get_result(job_id: str) -> Optional[Dict[str, Any]]:
    key = _result_key(job_id)
    data = redis_client.get(key)
    if data:
        return json.loads(data)
    return None


def list_jobs() -> list[dict]:
    jobs = []
    cursor = 0
    while True:
        cursor, keys = redis_client.scan(cursor=cursor, match="job:*:state", count=1000)
        for key in keys:
            job_id = key.decode().replace("job:", "").replace(":state", "")
            data = redis_client.get(key)
            if data:
                state = json.loads(data)
                jobs.append({
                    "job_id": job_id,
                    "status": state.get("status"),
                    "step": state.get("step"),
                    "progress_pct": state.get("progress_pct"),
                    "elapsed_s": int(time.time() - state["started_at"]) if "started_at" in state else None,
                    "object_name": state.get("object_name"),
                    "created_at": state.get("created_at"),
                })
        if cursor == 0:
            break
    # Newest first (jobs without a created_at sort last).
    jobs.sort(key=lambda j: j.get("created_at") or 0, reverse=True)
    return jobs


def delete_job(job_id: str) -> None:
    redis_client.delete(_state_key(job_id))
    redis_client.delete(_result_key(job_id))