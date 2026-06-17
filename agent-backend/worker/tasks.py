import gzip
import json
import os
import shutil
import threading
import time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

POLL_INTERVAL = 3
# Runaway guard: pi's `message_update` events re-serialize the whole growing message,
# so a generation loop (seen in the LaTeX/report step) balloons pi_events.jsonl to many
# GB and the job hangs to the timeout. Cap it: kill the job once the log crosses this.
MAX_EVENTS_BYTES = int(os.environ.get("MAX_EVENTS_BYTES", str(1024 * 1024 * 1024)))  # 1 GB

from .celery_app import celery_app
from app.job_store import set_state, set_result
from app.progress_feed import build_progress


def _finalize_events(events_path: Path) -> None:
    """Gzip the pi event log and drop the plain copy. It is a debug/progress artifact
    (the live feed already consumed it); compression keeps even a large log tiny on
    disk — repetitive event JSON shrinks ~50-100x."""
    try:
        if not events_path.exists():
            return
        with open(events_path, "rb") as fin, \
                gzip.open(str(events_path) + ".gz", "wb", compresslevel=6) as fout:
            shutil.copyfileobj(fin, fout, length=1024 * 1024)
        events_path.unlink()
    except Exception:
        pass


@celery_app.task(bind=True)
def run_pi_analysis(self, job_id: str):
    workspace_dir = Path(os.environ.get("WORKSPACE_DIR", "./workspaces"))
    workspace = workspace_dir / f"job_{job_id}"
    prompt = Path(os.environ.get("PROMPT_FILE", "./prompts/orchestrator.txt")).read_text().strip()
    model = os.environ.get("PI_MODEL", "llama.cpp-lab2/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf")
    timeout_s = int(os.environ.get("PI_TIMEOUT_SECONDS", 5400))

    set_state(
        job_id,
        status="running",
        step="Starting",
        progress_pct=2,
        started_at=time.time(),
    )

    pi_config_src = Path.home() / ".pi"
    pi_config_dst = workspace / ".pi"
    if not pi_config_dst.exists():
        pi_config_dst.symlink_to(pi_config_src, target_is_directory=True)

    env = os.environ.copy()
    env["VIDEO_PATH"] = "input_video.mp4"

    # Capture pi's JSON event stream so we can show a live, interactive feed of what
    # the agent is doing / thinking (see app/progress_feed.py).
    events_path = workspace / "pi_events.jsonl"
    events_file = open(events_path, "wb")

    proc = __import__("subprocess").Popen(
        ["pi", "-p", prompt, "--mode", "json", "--model", model],
        cwd=str(workspace),
        stdout=events_file,
        stderr=__import__("subprocess").PIPE,
        env=env,
    )

    stderr_lines = []

    def read_stderr():
        for raw in proc.stderr:
            line = raw.decode(errors="replace").strip()
            if line:
                stderr_lines.append(line)

    t_err = threading.Thread(target=read_stderr, daemon=True)
    t_err.start()

    deadline = time.time() + timeout_s

    while True:
        remaining = deadline - time.time()
        if remaining <= 0:
            proc.kill()
            try:
                events_file.close()
            except Exception:
                pass
            _finalize_events(events_path)
            set_state(job_id, status="failed", message="Timeout")
            return
        try:
            proc.wait(timeout=min(POLL_INTERVAL, remaining))
            break
        except __import__("subprocess").TimeoutExpired:
            pass

        # Runaway guard: stop a looping agent before it eats disk / hangs to timeout.
        try:
            evt_size = events_path.stat().st_size
        except OSError:
            evt_size = 0
        if evt_size > MAX_EVENTS_BYTES:
            proc.kill()
            try:
                events_file.close()
            except Exception:
                pass
            _finalize_events(events_path)
            mb = MAX_EVENTS_BYTES // (1024 * 1024)
            set_state(job_id, status="failed",
                      message=f"Stopped: agent output exceeded {mb} MB — likely a "
                              "report-generation loop. No partial result shipped.")
            return

        feed = build_progress(str(events_path), str(workspace))
        if feed:
            set_state(
                job_id,
                step=feed.get("step", "Running"),
                progress_pct=feed.get("progress_pct", 50),
                message=feed.get("message", ""),
                phase=feed.get("phase"),
                current_action=feed.get("current_action"),
                thinking=feed.get("thinking"),
                stages=feed.get("stages"),
                activities=feed.get("activities"),
                status="running",
            )

    try:
        events_file.close()
    except Exception:
        pass

    # pi has exited; the live feed is done with the log — archive it compressed.
    # (Every exit below this point is post-pi, so this single call covers them all.)
    _finalize_events(events_path)

    t_err.join(timeout=10)

    if proc.returncode != 0:
        msg = f"Pi exited with code {proc.returncode}"
        if stderr_lines:
            stderr_text = "\n".join(stderr_lines)[:500]
            msg += f": {stderr_text}"
        set_state(job_id, status="failed", message=msg)
        return

    stats_path = workspace / "analysis_output" / "data" / "stats.json"
    if not stats_path.exists():
        set_state(job_id, status="failed", message="stats.json not found")
        return

    stats = json.loads(stats_path.read_text())

    extractor_prompt = Path(os.environ.get("EXTRACTOR_PROMPT_FILE", "./prompts/job-output-extractor.txt")).read_text().strip()
    extractor_input = f"{extractor_prompt}\n\njob_id={job_id}"
    extractor_env = env.copy()
    extractor_env["job_id"] = job_id
    extractor_env["OUTPUT_STUDENT_PDF"] = "analysis_output/report/student_edition.pdf"
    extractor_env["OUTPUT_TEACHER_PDF"] = "analysis_output/report/teacher_key.pdf"
    extractor_env["OUTPUT_ANNOTATED_VIDEO"] = "analysis_output/video_annotation/annotated_video.mp4"
    extractor_env["OUTPUT_SUMMARY_PANEL"] = "analysis_output/plots/summary_panel.png"
    extractor_env["OUTPUT_KINEMATICS_CSV"] = "analysis_output/data/kinematics.csv"

    ep = __import__("subprocess").Popen(
        ["pi", "-p", extractor_input, "--mode", "text", "--model", model],
        cwd=str(workspace),
        stdout=__import__("subprocess").PIPE,
        stderr=__import__("subprocess").PIPE,
        env=extractor_env,
    )
    try:
        e_stdout, e_stderr = ep.communicate(timeout=120)
    except __import__("subprocess").TimeoutExpired:
        ep.kill()
        set_state(job_id, status="failed", message="Extractor timeout")
        return

    if ep.returncode != 0:
        msg = f"Extractor exited with code {ep.returncode}"
        if e_stderr:
            msg += f": {e_stderr.decode(errors='replace')[:200]}"
        set_state(job_id, status="failed", message=msg)
        return

    files = _parse_extractor_output(e_stdout.decode(errors="replace"), job_id, str(workspace))
    if not files:
        set_state(job_id, status="failed", message="Extractor returned no files")
        return

    set_result(job_id, stats=stats, files=files)
    set_state(job_id, status="done", progress_pct=100, step="Complete")


def _parse_extractor_output(output: str, job_id: str, workspace_path: str) -> dict | None:
    import re
    m = re.search(r"\{[\s\S]*\"files\"[\s\S]*\}", output)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None

    fallback = {
        "student_pdf": "analysis_output/report/student_edition.pdf",
        "teacher_pdf": "analysis_output/report/teacher_key.pdf",
        "annotated_video": "analysis_output/video_annotation/annotated_video.mp4",
        "summary_panel": "analysis_output/plots/summary_panel.png",
        "kinematics_csv": "analysis_output/data/kinematics.csv",
    }
    found = data.get("files", {})
    files_dict = {}
    url_prefix = f"/files/job_{job_id}"
    for key in ("student_pdf", "teacher_pdf", "annotated_video", "summary_panel", "kinematics_csv"):
        entry = found.get(key, {})
        if entry.get("found"):
            path = entry["path"]
            # The extractor reports paths relative to the workspace (its cwd);
            # make it absolute first, otherwise os.path.relpath resolves against
            # the worker's cwd (/app) and produces ../../ traversals that
            # Starlette's StaticFiles blocks at serve time.
            if not os.path.isabs(path):
                path = os.path.join(workspace_path, path)
            rel = os.path.relpath(path, workspace_path)
            # Belt: if os.path.relpath still produced an escape (e.g. workspace
            # itself is a symlink chain), normalize it away and fall back to the
            # hardcoded relative path.
            if rel.startswith(".."):
                rel = fallback.get(key, "")
            files_dict[key] = f"{url_prefix}/{rel}"
        else:
            files_dict[key] = f"{url_prefix}/{fallback[key]}"
    return files_dict
