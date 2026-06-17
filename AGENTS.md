# AGENTS.md — operating guide for AI agents working in `~/centri`

Orientation + conventions for an AI coding agent (e.g. Claude Code) working on Centri. Read `README.md` first for the product/architecture; this file is the *how to work here* layer.

## What this is

Centri measures circular-motion physics from a phone video and tutors the student. Five pieces (see `README.md` for the diagram):
- `app/` — Flutter app (Android). The product UI.
- `agent-backend/` — measurement backend (FastAPI + Celery + the `pi` agent), **runs in Docker**.
- `pedagogy-backend/` — tutor backend (FastAPI, Socratic inquiry).
- `sam3/` — object tracker (C++/CUDA), **symlink** to `~/sams2/sam3cpp`.
- `archive/` — superseded code; don't build on it.

## Environments & how to run

- **Python (both backends + SAM3 server):** conda env `sam3` → `~/miniconda3/envs/sam3/bin/python`. It has fastapi/uvicorn/celery/redis/opencv/etc. There is **no project venv**.
- **agent-backend:** `cd ~/centri/agent-backend && docker compose up -d redis api worker`. `pi` runs **inside the worker container** (the image installs it). Code in `app/`, `worker/`, `prompts/`, `templates/`, `.pi/` is **bind-mounted** → edits to `routes.py`/`prompts/*` take effect without a rebuild, but **restart the container** for anything Python imports at load (`docker compose restart api|worker`). `prompts/orchestrator.txt` is read fresh per job (no restart needed).
- **pedagogy-backend:** `cd ~/centri/pedagogy-backend && ~/miniconda3/envs/sam3/bin/python -m uvicorn main:app --host 192.168.1.13 --port 8090`. Needs `.env` (Qwen URL + key).
- **SAM3:** `~/centri/sam3/run_sam3.sh` (supervisor loop; auto-relaunches; `POST /reset` recycles it).
- **app:** `cd ~/centri/app && flutter run -d <device>` (Flutter at `/opt/flutter`, invoke as `env FLUTTER_ROOT=/opt/flutter /opt/flutter/bin/flutter`). Build APK: `flutter build apk --debug`.

Bind to the **LAN IP `192.168.1.13`**, never `0.0.0.0` (user preference). The phone reaches the backends over wifi; ports need `ufw allow from 192.168.1.0/24`.

## Conventions

- **UI copy reads like a teacher, not a terminal.** Education/learning language everywhere user-facing (progress feed, worksheet, tutor). Hide raw shell commands. Keep real physics notation (ω, aᶜ, LaTeX). Applies to `app/`, `agent-backend/app/progress_feed.py`, and the pedagogy/orchestrator prompts.
- **Results are data-driven & native.** The app renders charts (`fl_chart`), tables, and the worksheet from `/result`'s structured `series` + `worksheet`; only the annotated video is a baked artifact. Don't reintroduce the summary-panel PNG / PDFs into the UI.
- **The user-marked rotation centre is authoritative** (sent as `rotation_center_frac`); the reference object is for scale only. Don't let RANSAC or verify override a user mark.
- **Never fabricate physics.** The orchestrator gate aborts below a tracking-coverage floor rather than emitting garbage.

## Gotchas (will bite you)

- **`video_thumbnail` pub-cache hack:** the Android build needs a manual patch to `~/.pub-cache/hosted/pub.dev/video_thumbnail-0.5.6/android/build.gradle` (strip its `buildscript`/jcenter, `compileSdkVersion 36`). **`flutter pub get` reverts it** → re-apply, or the build fails on `:video_thumbnail`.
- **`pkill -f "<pattern>"`** matches the agent's own shell when the pattern text is in your command → it kills your command (exit 144). Kill by **port** (`ss -tlnp | grep :PORT`) or PID instead.
- **Inference `192.168.1.205:8083` is external and unstable** — crashes under load (model unloads). Verify it generates before debugging "empty/failed" agent output.
- **Shared GPU** — SAM3 + inference + sometimes a game contend; interactive calls (suggest/tutor) starve during a long analysis job.
- **USB to the Nokia drops** mid-`flutter run` ("Lost connection"); the APK still installs. A fresh `flutter run` or `adb install -r` works; hot reload via `kill -USR1 <flutter_pid>`, hot restart `-USR2`.
- **SAM3 coverage decays** over the server's lifetime; a restart fully recovers it (the gate auto-recycles via `/reset`).

## Validate before declaring done

- Backend Python: `~/miniconda3/envs/sam3/bin/python -c "import ast; ast.parse(open('<file>').read())"` (base python lacks deps).
- Flutter: `env FLUTTER_ROOT=/opt/flutter /opt/flutter/bin/flutter analyze <files>`.
- Health probes: sam3 `:8086/health`, agent-api `:8088` (422 on bare `/verify-objects` = up), pedagogy `:8090/health`.
