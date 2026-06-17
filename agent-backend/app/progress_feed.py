"""Deterministic progress feed for the agentic pipeline.

The `pi` agent emits a JSON event stream on stdout (one event per line). The worker
redirects that stream to ``<workspace>/pi_events.jsonl``. This module turns that raw
stream — plus the files the agent has produced so far — into a compact, human-readable
view of what the agent is doing right now, what it is thinking, and what is already done.

This replaces the old approach of asking the VLM to summarise a log tail on every poll
(slow, costly, and competing with the pipeline for the GPU). Parsing here is pure Python:
cheap enough to run every couple of seconds.
"""
import json
import os
from pathlib import Path

# Keep the live feed bounded so /status payloads stay small.
MAX_ACTIVITIES = 60
THINKING_CHARS = 280

# The named stages a student sees, in order. Each maps loosely to the orchestrator's
# Steps 1-8 + subagents + report, but is phrased for a non-expert.
STAGES = [
    ("inspect", "Look at the video"),
    ("track", "Follow the moving object"),
    ("trajectory", "Find the circular path"),
    ("kinematics", "Measure speed & acceleration"),
    ("visuals", "Draw the motion & graphs"),
    ("report", "Write up the results"),
]


def _basename(path: str) -> str:
    return os.path.basename(path.rstrip("/")) or path


def _humanize_bash(cmd: str) -> tuple[str, str]:
    """Map a shell command to a (kind, friendly title)."""
    c = cmd.strip()
    low = c.lower()
    if "ffprobe" in low:
        return "run", "Looking at your video"
    if "/track" in low or "tracking_api" in low or ("requests.post" in low and "track" in low):
        return "track", "Following the moving object"
    if "pdflatex" in low or "latexmk" in low or "xelatex" in low:
        return "write", "Writing up your results"
    if "ffmpeg" in low:
        return "run", "Drawing on your video"
    # python step scripts → "Calculating the motion"
    if (".py" in low or low.startswith("python")):
        return "run", "Calculating the motion"
    if low.startswith(("cat ", "ls", "head ", "tail ", "grep ", "find ")):
        return "read", "Checking the results so far"
    if low.startswith(("mkdir", "cp ", "mv ", "touch")):
        return "run", "Getting set up"
    if "subagent" in low or "spawn" in low or ("pi " in low and "--mode" in low):
        return "run", "Creating plots, video & questions"
    if low.startswith("cd "):
        return "run", "Working on the analysis"
    # fallback: never surface a raw shell command in the student-facing title.
    return "run", "Working on the analysis"


def _humanize_tool(tool_name: str, args: dict) -> tuple[str, str, str]:
    """Return (kind, title, detail) for a tool_execution_start event."""
    if tool_name == "bash":
        cmd = (args or {}).get("command", "")
        kind, title = _humanize_bash(cmd)
        return kind, title, cmd
    if tool_name == "read":
        path = (args or {}).get("path", "")
        return "read", "Checking the results so far", _basename(path)
    if tool_name in ("write", "edit"):
        path = (args or {}).get("path", "")
        return "write", "Saving your results", _basename(path)
    if tool_name in ("task", "agent", "subagent"):
        return "run", "Working on a sub-task", ""
    return "run", "Working", ""


def _detect_stages(workspace: Path, activities: list) -> tuple[list, str, int]:
    """Infer stage statuses from the files produced + actions taken.

    Returns (stages, phase_key, progress_pct).
    """
    def exists(*parts) -> bool:
        return (workspace.joinpath(*parts)).exists()

    def any_glob(pat) -> bool:
        return any(workspace.glob(pat))

    # Evidence that each stage has produced output (done) or merely started.
    done = {
        "inspect": exists("step1.py") or any_glob("*probe*.json") or any_glob("video_meta*.json"),
        "track": any_glob("**/api_cache.json") or any_glob("**/*trajectory*raw*") or exists("step2.py"),
        "trajectory": any_glob("**/*trajectory*clean*") or any_glob("**/*trajectory*.csv") or exists("step5.py"),
        "kinematics": any_glob("**/kinematics.csv") or any_glob("**/stats.json"),
        "visuals": any_glob("**/summary_panel.png") or any_glob("**/annotated_video.mp4") or any_glob("**/*.png"),
        "report": any_glob("**/*.pdf"),
    }

    # An action keyword hints which stage is currently active even before output lands.
    last_titles = " ".join(a.get("title", "").lower() for a in activities[-6:])
    active_hint = None
    if "track" in last_titles:
        active_hint = "track"
    elif "report" in last_titles or "pdf" in last_titles or "latex" in last_titles:
        active_hint = "report"
    elif "plot" in last_titles or "annotat" in last_titles:
        active_hint = "visuals"
    elif "video propert" in last_titles or "inspecting video" in last_titles:
        active_hint = "inspect"

    stages = []
    n_done = 0
    active_assigned = False
    for key, label in STAGES:
        if done[key]:
            status = "done"
            n_done += 1
        elif not active_assigned and (active_hint == key or all(
            done[k] for k, _ in STAGES[: [s[0] for s in STAGES].index(key)]
        )):
            # first not-done stage whose predecessors are done (or hinted) is active
            status = "active"
            active_assigned = True
        else:
            status = "pending"
        stages.append({"key": key, "label": label, "status": status})

    # progress: stages carry the bulk; nudge a little while a stage is active.
    pct = int(round(100 * n_done / len(STAGES)))
    if active_assigned and pct < 100:
        pct = min(99, pct + 6)
    pct = max(pct, 2)

    phase = next((s["key"] for s in stages if s["status"] == "active"),
                 "report" if n_done == len(STAGES) else "inspect")
    return stages, phase, pct


def _read_reported(workspace: Path) -> dict | None:
    """The agent's own progress report — authoritative, written per step into the
    workspace. Shape: {"stage": <one of STAGES keys>, "note": str, "pct": int}.

    Co-locating this with the agent (it runs in the worker container, same FS) means
    a single writer (the worker's build_progress) — no race with an HTTP endpoint.
    """
    f = workspace / ".centri_progress.json"
    if not f.exists():
        return None
    try:
        d = json.loads(f.read_text(errors="replace"))
    except Exception:
        return None
    return d if isinstance(d, dict) else None


def build_progress(events_path: str, workspace_path: str) -> dict:
    """Parse the pi event stream + workspace into a live progress view."""
    ev = Path(events_path)
    workspace = Path(workspace_path)

    activities: list[dict] = []
    by_id: dict[str, dict] = {}
    last_thinking = ""
    last_text = ""
    seq = 0

    if ev.exists():
        with open(ev, "r", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                t = d.get("type")

                if t == "tool_execution_start":
                    seq += 1
                    kind, title, detail = _humanize_tool(d.get("toolName", ""), d.get("args"))
                    item = {
                        "seq": seq,
                        "kind": kind,
                        "title": title,
                        "detail": (detail or "")[:200],
                        "status": "running",
                    }
                    cid = d.get("toolCallId")
                    if cid:
                        by_id[cid] = item
                    activities.append(item)

                elif t == "tool_execution_end":
                    cid = d.get("toolCallId")
                    item = by_id.get(cid)
                    if item is not None:
                        item["status"] = "error" if d.get("isError") else "done"

                elif t == "text":
                    txt = (d.get("text") or "").strip()
                    if txt:
                        last_text = txt

                elif t == "message_update":
                    ame = d.get("assistantMessageEvent") or {}
                    partial = ame.get("partial") or {}
                    for block in (partial.get("content") or []):
                        if isinstance(block, dict) and block.get("type") == "thinking":
                            think = block.get("thinking") or ""
                            if think:
                                last_thinking = think

                elif t == "message_end":
                    msg = d.get("message") or {}
                    if msg.get("role") == "assistant":
                        for block in (msg.get("content") or []):
                            if not isinstance(block, dict):
                                continue
                            if block.get("type") == "text":
                                txt = (block.get("text") or "").strip()
                                if txt:
                                    last_text = txt
                            elif block.get("type") == "thinking":
                                think = (block.get("thinking") or "").strip()
                                if think:
                                    last_thinking = think

    # Trim the feed.
    activities = activities[-MAX_ACTIVITIES:]

    stages, phase, pct = _detect_stages(workspace, activities)

    # The agent reports its own stage/note (authoritative + monotonic); the file-glob
    # heuristic above is the fallback for the gaps between reports.
    reported = _read_reported(workspace)
    reported_note = None
    if reported:
        keys = [k for k, _ in STAGES]
        rstage = reported.get("stage")
        if rstage in keys:
            idx = keys.index(rstage)
            stages = [
                {"key": k, "label": lbl,
                 "status": "done" if i < idx else ("active" if i == idx else "pending")}
                for i, (k, lbl) in enumerate(STAGES)
            ]
            phase = rstage
            rpct = reported.get("pct")
            if isinstance(rpct, (int, float)):
                pct = max(2, min(99, int(rpct)))
        note = reported.get("note")
        if isinstance(note, str) and note.strip():
            reported_note = note.strip()

    # Current action: the agent's own note wins; else a running tool; else narration.
    running = next((a for a in reversed(activities) if a["status"] == "running"), None)
    if reported_note:
        current_action = reported_note
    elif running:
        current_action = running["title"]
    elif last_text:
        current_action = last_text.split("\n", 1)[0][:120]
    elif last_thinking:
        current_action = "Thinking…"
    else:
        current_action = "Starting…"

    # A short "thinking" snippet = the most recent reasoning (tail, where the live edge is).
    thinking = ""
    if last_thinking:
        tail = last_thinking.strip().replace("\n", " ")
        thinking = ("…" + tail[-THINKING_CHARS:]) if len(tail) > THINKING_CHARS else tail

    phase_label = next((lbl for k, lbl in STAGES if k == phase), "Working")

    return {
        # back-compat fields
        "step": phase_label,
        "progress_pct": pct,
        "message": current_action,
        # rich fields
        "phase": phase,
        "current_action": current_action,
        "thinking": thinking,
        "stages": stages,
        "activities": activities,
    }
