"""Adapter: agent-backend measurement output → MeasurementContext (the seam).

Lets the tutor auto-populate the physics context from a completed analysis job
instead of the caller passing it manually.
"""
import requests

from . import config
from .inquiry.schemas import MeasurementContext


def fetch_measurement(job_id):
    """GET agent-backend /result/{job_id} and build a MeasurementContext from its stats."""
    url = config.AGENT_BACKEND_URL.rstrip("/") + f"/result/{job_id}"
    headers = {"X-API-Key": config.AGENT_BACKEND_KEY} if config.AGENT_BACKEND_KEY else {}
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    stats = resp.json().get("stats", {}) or {}
    return MeasurementContext.from_agent_stats(stats)
