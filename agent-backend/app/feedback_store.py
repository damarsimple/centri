"""Append-only feedback/telemetry sink for the human-in-the-loop pilot.

Two event types land here:
  - "setup_correction": what the VLM/SAM3 predicted vs. what the student actually
    submitted (implicit labels for where vision goes wrong).
  - "result_feedback": a student/teacher flagging an analysis result as wrong.

Stored as JSONL so it survives the workspace TTL cleanup and is trivial to analyze
later. Swap the backend (DB, object store) by changing only this module.
"""
import json
import os
import time
import uuid
from pathlib import Path

FEEDBACK_DIR = Path(os.environ.get("FEEDBACK_DIR", "./feedback"))
FEEDBACK_FILE = FEEDBACK_DIR / "feedback.jsonl"


def store(event: dict) -> str:
    FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
    fid = str(uuid.uuid4())
    record = {"id": fid, "ts": time.time(), **event}
    with open(FEEDBACK_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return fid
