import json
import os
import time
import requests
from pathlib import Path

PROMPT = """You are analyzing a live log file from a video analysis pipeline. The pipeline has these phases with approximate percentage ranges:

1. Code generation (0-20%): Writing step scripts (step1 through step8)
2. Sequential execution (20-88%): Running steps 1-8 (scene parsing, ROI crop, coord validation, pre-calibration, trajectory cleaning, calibration, active interval detection, kinematics & summary)
3. Subagents (88-95%): Running 3 subagents in parallel (video annotation, figure generation, question generation)
4. LaTeX compilation (95-98%): Compiling student_edition.tex and teacher_key.tex
5. Report finalization (98-100%): Writing report.md

Read the log tail below and determine the CURRENT state. Return ONLY valid JSON with these fields:
- "step": short step name like "Code generation" or "Running step 3"
- "progress_pct": integer 0-100
- "message": one-line status description

Log tail:
"""

ANALYSIS_CACHE_TTL = 30


def find_session_file(job_id: str) -> Path | None:
    session_dir = Path.home() / ".pi" / "agent" / "sessions" / f"--app-workspaces-job_{job_id}--"
    if not session_dir.is_dir():
        return None
    files = sorted(session_dir.glob("*.jsonl"))
    return files[-1] if files else None


def tail_session_file(file_path: Path, max_chars: int = 12000) -> str:
    if not file_path.exists():
        return ""
    size = file_path.stat().st_size
    if size <= max_chars:
        raw = file_path.read_text(errors="replace")
    else:
        with open(file_path, "rb") as f:
            f.seek(-max_chars, os.SEEK_END)
            raw = f.read(max_chars).decode(errors="replace")
        idx = raw.find("\n")
        if idx > 0 and idx < len(raw) - 1:
            raw = raw[idx + 1:]

    lines = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        msg = entry.get("message", {})
        if msg.get("role") == "assistant":
            content = msg.get("content", [])
            for block in content:
                if block.get("type") in ("thinking", "text"):
                    text = block.get("thinking", "") or block.get("text", "")
                    lines.append(text)
                elif block.get("type") == "toolCall":
                    lines.append(f"[TOOL] {block.get('name', '')}: {block.get('arguments', {}).get('command', '')}")
        elif msg.get("role") == "toolResult":
            for block in msg.get("content", []):
                if block.get("type") == "text":
                    lines.append(block.get("text", ""))

    return "\n".join(lines[-100:])


TEMPERATURE = float(os.environ.get("PI_ANALYZER_TEMPERATURE", 1.0))
MAX_TOKENS = int(os.environ.get("PI_ANALYZER_MAX_TOKENS", 10000))
REQUEST_TIMEOUT = int(os.environ.get("PI_ANALYZER_TIMEOUT", 90))


def infer_progress(log_tail: str) -> dict:
    inference_url = os.environ.get("PI_INFERENCE_URL", "http://192.168.1.205:8083")
    model = os.environ.get("PI_INFERENCE_MODEL", "Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf")
    api_key = os.environ.get("PI_INFERENCE_API_KEY", "")
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    try:
        resp = requests.post(
            f"{inference_url}/v1/chat/completions",
            headers=headers,
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "You are a log analyzer. Output only JSON. Do not include thinking or reasoning."},
                    {"role": "user", "content": PROMPT + log_tail},
                ],
                "temperature": TEMPERATURE,
                "max_tokens": MAX_TOKENS,
            },
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code != 200:
            return {}
        body = resp.json()
        msg = body.get("choices", [{}])[0].get("message", {})
        text = msg.get("content", "").strip()
        if not text:
            text = msg.get("reasoning_content", "").strip()
        text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return json.loads(text)
    except Exception as e:
        return {}


def analyze_progress(job_id: str, workspace_dir: str) -> dict:
    sf = find_session_file(job_id)
    if sf is None:
        return {}
    log_tail = tail_session_file(sf)
    if not log_tail:
        return {}
    return infer_progress(log_tail)
