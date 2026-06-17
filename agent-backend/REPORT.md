# Pi Circular Motion Analysis Pipeline — Full System Report

> **Update (2026-06-04) — current-state delta since this report was written.** The
> sections below remain accurate on the pipeline internals; these are the changes layered
> on top. Project-level docs now live at `~/centri/README.md`, `AGENTS.md`, `REPORT.md`.
> - **Runs in Docker** (`docker compose up -d redis api worker`); `pi` runs inside the
>   worker container. Code is bind-mounted; `prompts/orchestrator.txt` is read per-job.
> - **API on `192.168.1.13:8088`** (LAN-bound, not 0.0.0.0).
> - **Tracking-coverage gate + retry** in Step 2: SAM3 is non-deterministic, so `/track`
>   is wrapped in a coverage check (accept ≥85%, retry ≤3 keeping the best, **abort <50%**),
>   and recycles the SAM3 server via `/reset` between retries (SAM3 degrades over its lifetime).
> - **User-marked rotation centre is authoritative** (`rotation_center_frac`); the
>   reference object is used for scale only.
> - **`/result` now returns structured data** (`series` for native charts + `worksheet`
>   with answers/solutions) so the app renders native UI instead of the PNG/PDF.
> - **`/suggest-scene` + `/verify-objects`** offloaded to a threadpool (the blocking
>   VLM/SAM calls were freezing the event loop). `/suggest-scene` uses `/no_think` + a token cap.
> - **Live, education-language progress feed** (`app/progress_feed.py`) + the agent's own
>   per-step progress reports drive the app's interactive progress view.

## 1. Project Overview

This system is a **video-based physics analysis pipeline** that takes smartphone videos of objects rotating on a lazy-susan turntable, runs computer vision tracking powered by an LLM agent (Pi), produces kinematics data (radius, angular velocity, centripetal acceleration, period), and generates **student/teacher LaTeX reports** with annotated videos and plots.

The pipeline is orchestrated by **Pi** (`@earendil-works/pi-coding-agent`), an LLM-based coding agent that generates and executes Python/ffmpeg scripts step-by-step. The backend wraps Pi in a **FastAPI + Celery + Redis** architecture for job submission, queueing, progress tracking, and result delivery.

### 1.1. Key Technologies

| Component | Technology |
|-----------|-----------|
| API Server | FastAPI (Python 3.12) |
| Task Queue | Celery 5.x with Redis broker |
| Cache/Database | Redis 7 (ephemeral, TTL-based) |
| Containerization | Docker Compose (4 services) |
| LLM Agent | Pi coding agent (Node.js, npm global) |
| Inference | llama.cpp server (OpenAI-compatible) |
| Tracking API | SAM 3 CPP (custom C++ tracking) |
| LaTeX Compilation | latex-document-skill (`compile_latex.sh`) |
| Reverse Proxy | socat tunnels on lab1 |
| Scientific Stack | OpenCV, NumPy, SciPy, scikit-learn, Matplotlib |
| Video Processing | ffmpeg |

### 1.2. Network Topology

```
Internet (Tailscale Funnel / socat)
    │
    ├── lab1 (Arch Linux, 10.0.0.1, public 140.115.126.111)
    │     ├── socat-proxy (port 8082 → 10.0.0.2:8000)  [open to all]
    │     └── socat-llama (port 8084 → 192.168.1.205:8083)  [restricted]
    │
    ├── lab2 (10.0.0.2) — DOCKER HOST
    │     ├── agent-backend-api-1 (8000)
    │     ├── agent-backend-worker-1
    │     ├── agent-backend-beat-1
    │     └── agent-backend-redis-1
    │
    └── llama-server (192.168.1.205:8083) — Qwen3 35B A3B Q4_K_XL
```

---

## 2. Architecture

### 2.1. Services (Docker Compose)

```
docker-compose.yml defines 4 services + 1 optional:
```

**`redis`** — Redis 7 Alpine, healthcheck every 5s. Stores job state, results, and Celery task queue.

**`api`** — FastAPI server on port 8000. Handles all HTTP endpoints. Mounts `app/`, `worker/`, `prompts/`, `templates/`, `.pi/`, `workspaces/`, `latex-skill/` as volumes.

**`worker`** — Celery worker with `--concurrency=1` (single job at a time). Runs the Pi analysis subprocess. Same volume mounts as API.

**`beat`** — Celery beat scheduler. Periodically runs `cleanup_expired_workspaces` (every hour) to delete workspaces older than `WORKSPACE_TTL_HOURS` (default 24h).

**`caddy`** (profile: production only) — Caddy 2 reverse proxy for HTTPS. Requires `DOMAIN` env var. Profiles prevent it from starting in dev mode.

### 2.2. Data Flow

```
Client → POST /analyze (video + sidecar + template)
         │
         ├── FastAPI validates video type/size
         ├── Creates workspace dir from template
         ├── Writes input_video.mp4 and sidecar.json
         └── Enqueues Celery task (run_pi_analysis)
         
         Worker picks up task:
         ├── Sets Redis state = "running"
         ├── Symlinks .pi/ config into workspace
         ├── Spawns `pi` subprocess (--mode json)
         ├── Polls every 30s via progress_analyzer
         │     └── Reads Pi session JSONL → LLM infers step/progress
         ├── On completion:
         │     ├── Reads stats.json
         │     └── Runs extractor subprocess
         │           └── Returns file paths → stored in Redis result
         └── Sets Redis state = "done" with result

Client → GET /status/{job_id}        ← Redis state
Client → GET /result/{job_id}        ← Redis result (stats + file URLs)
Client → GET /jobs                   ← Redis SCAN all job:*:state
Client → DELETE /job/{job_id}        ← Removes workspace + Redis keys
```

### 2.3. Redis Schema

```
job:{job_id}:state   → JSON: { status, step, progress_pct, message, started_at }
job:{job_id}:result  → JSON: { stats: {...}, files: {...} }
  TTL: 48h (configurable via JOB_STATE_TTL / JOB_RESULT_TTL)
```

---

## 3. API Endpoints

| Method | Path | Rate Limit | Description |
|--------|------|------------|-------------|
| POST | `/analyze` | 10/min | Submit video for analysis |
| GET | `/status/{job_id}` | 30/min | Get job progress |
| GET | `/result/{job_id}` | 30/min | Get completed job results |
| GET | `/jobs` | 30/min | List all jobs |
| DELETE | `/job/{job_id}` | 10/min | Delete job and workspace |

All endpoints require `X-API-Key` header (configurable via `API_KEY` env var).

### 3.1. POST /analyze

**Parameters** (multipart form):
- `video` — MP4/MOV/AVI/MKV file, max 500MB
- `sidecar` — JSON string with experiment metadata
- `template` — Template directory name (e.g., `basetemplate-turntable-1`)

**Sidecar JSON format:**
```json
{
  "title": "Centripetal Motion Analysis",
  "student_name": "",
  "setup_text": "...",
  "theory_text": "...",
  "experiment_description": "...",
  "inferences": {
    "conclusion_summary": "...",
    "error_analysis": "...",
    "real_world_applications": "..."
  }
}
```

**Template sanitization**: Blocks `..` and `/` in template name; validates resolved path stays under `TEMPLATE_DIR` parent.

### 3.2. GET /status/{job_id}

Returns:
```json
{
  "job_id": "...",
  "status": "running|done|failed",
  "step": "Code generation|Running step 3|LaTeX compilation|...",
  "progress_pct": 0-100,
  "message": "...",
  "elapsed_s": 1234
}
```

Progress is inferred by sending the tail of Pi's session JSONL file to the LLM, which returns structured JSON with step, progress_pct, and message. The progress analyzer prompt maps pipeline stages to percentage ranges:

| Phase | % Range | Description |
|-------|---------|-------------|
| Code generation | 0–20% | Writing step1–step8 scripts |
| Sequential execution | 20–88% | Running steps 1–8 |
| Subagents | 88–95% | 3 parallel subagents |
| LaTeX compilation | 95–98% | Compiling PDFs |
| Report finalization | 98–100% | Writing report.md |

### 3.3. GET /result/{job_id}

Returns:
```json
{
  "job_id": "...",
  "stats": { ... kinematics data ... },
  "files": {
    "student_pdf": "/files/job_xxx/analysis_output/report/student_edition.pdf",
    "teacher_pdf": "/files/job_xxx/analysis_output/report/teacher_key.pdf",
    "annotated_video": "/files/job_xxx/analysis_output/video_annotation/annotated_video.mp4",
    "summary_panel": "/files/job_xxx/analysis_output/plots/summary_panel.png"
  }
}
```

Static files are served directly by FastAPI via `app.mount("/files", StaticFiles(...))`.

---

## 4. Pi Pipeline (The Orchestrator)

The orchestrator prompt (`prompts/orchestrator.txt`, 1174 lines) defines an 8-step pipeline executed by the Pi agent:

### Step 1: Scene Parsing
- Analyzes the input video frame-by-frame using the tracking API
- Identifies the rotating object, estimates physical size
- Outputs: bounding box, object description, size estimate

### Step 2: ROI Crop
- Uses ffmpeg to crop the video to the region of interest
- Handles coordinate conversion between cropped and original space
- Passes crop parameters to downstream tracking

### Step 3: Coordinate Validation
- Extracts 5 sample frames for manual coordinate verification
- Generates annotated images showing tracked points
- User (Pi) reviews and corrects if needed

### Step 4: Pre-Calibration
- Validates tracking center and pixel-to-meter scale
- Performs initial quality checks

### Step 5: Trajectory Cleaning
- RANSAC-based outlier rejection on tracking data
- Fits circle to trajectory points
- Computes center drift between calibration and fit

### Step 6: Calibration
- Determines final pixel-to-meter conversion
- Validates physical size assumptions

### Step 7: Active Interval Detection
- Identifies frames where object is actively rotating
- Filters out stationary/transition periods

### Step 8: Kinematics & Summary
- Computes radius, angular velocity (omega), centripetal acceleration
- FFT-based period detection
- Phase analysis (stable/increasing/decreasing omega)
- Validation flags for quality assessment

### Parallel Subagents (step 88-95%)
After the main 8 steps, 3 subagents run in parallel via Pi's `subagent` tool:
1. **Video Annotation** — Overlays tracking data, vectors, and HUD on video
2. **Figure Generation** — Creates plots (trajectory, radius vs time, omega vs time, theta vs time, centripetal acceleration vs time, summary panel, annotated image, annotated table)
3. **Question Generation** — Generates student worksheet questions

### LaTeX Compilation (step 95-98%)
Uses `compile_latex.sh` from the latex-document-skill. The script:
- Auto-detects LaTeX engine (pdflatex/xelatex/lualatex)
- Runs `--use-latexmk` when available for automatic multi-pass resolution
- Falls back to its own multi-pass logic (bibliography, index, glossary detection)
- Generates PNG preview images alongside PDFs
- Handles error recovery and provides diagnostics

The orchestrator compiles two documents:
1. `student_edition.tex` — Worksheet for students
2. `teacher_key.tex` — Answer key with solutions

### Job Output Extractor
After the main pipeline exits, a separate Pi subprocess (mode `--mode text`) runs with `prompts/job-output-extractor.txt` (80 lines). This read-only agent:
- Scans the workspace for output files
- Returns structured JSON with file paths and metadata
- Falls back to default paths if files not found

### Known Limitation: Subagent Trace Visibility
Subagents spawned via Pi's `subagent` tool run inline within the orchestrator's LLM context. Their intermediate reasoning is embedded in the main session file's large JSONL response lines but is not stored in separate session files. Only final subagent outputs are captured in the main session.

---

## 5. Infrastructure

### 5.1. Docker Host (lab2, 10.0.0.2)

The Docker Compose stack runs on lab2, a machine on the internal 10.0.0.0/24 network. All services use the default bridge network with host port mappings.

**Volume mounts:**
- `./app:/app/app` — API code (live-reload capable)
- `./worker:/app/worker` — Worker code
- `./prompts:/app/prompts` — Orchestrator and extractor prompts
- `./templates:/app/templates` — Template directories with sample videos
- `./.pi:/root/.pi` — Pi config, subagent definitions, and session files
- `./workspaces:/app/workspaces` — Per-job workspaces (ephemeral, TTL 24h)
- `./latex-skill:/latex-skill:ro` — LaTeX skill scripts and templates

### 5.2. Inference Server (llama.cpp, 192.168.1.205:8083)

- **Model**: Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf (quantized, 4-bit)
- **API**: OpenAI-compatible `/v1/chat/completions`
- **Auth**: `Authorization: Bearer lazailai`
- **Pi model config**: Stored in `config/pi-models.json`, baked into Docker image at `/root/.pi/agent/models.json`

The model uses a "thinking" mode (`reasoning_content` field). The progress analyzer requires `PI_ANALYZER_MAX_TOKENS=10000` to ensure JSON output appears in the `content` field rather than being consumed by the reasoning tokens.

### 5.3. Tracking API (SAM 3 CPP, 192.168.1.13:8086)

A custom C++ server running a SAM-based point tracking model. Receives cropped video frames and returns pixel coordinates of tracked points.

### 5.4. Reverse Proxy Tunnels (lab1, 10.0.0.1)

Two socat tunnels run as systemd services on lab1 (Arch Linux, public IP 140.115.126.111):

**socat-proxy.service** — API tunnel
- `src 0.0.0.0:8082 → dst 10.0.0.2:8000`
- UFW: open to all
- Use case: Public API endpoint (or Tailscale Funnel alternative)

**socat-llama.service** — Llama tunnel
- `src 0.0.0.0:8084 → dst 192.168.1.205:8083`
- UFW: allow only `10.0.0.2` and `140.115.126.108`
- Use case: Restricted inference endpoint for external clients

Both tunnels document full systemd unit files in `docs/tunneling.md`.

### 5.5. UFW Configuration (lab1)

Default policy: DROP inbound. Specific allows for the two socat ports plus the upstream router (140.115.126.254) which blocks inbound by default. Tailscale Funnel was evaluated as an alternative for public exposure without router configuration changes.

---

## 6. Template System

### 6.1. Template Directory Structure

```
templates/
├── base-template-bicycle/          — Experimental (bicycle analysis)
├── basetemplate-turntable-1/       — Template 1: IMG_3071.mp4 (red phone)
│   ├── IMG_3071.mp4                (4.6 MB)
│   └── sidecar.json
├── basetemplate-turntable-2/       — Template 2: IMG_3072.mp4
│   ├── IMG_3072.mp4                (3.5 MB)
│   └── sidecar.json
└── basetemplate-turntable-3/       — Template 3: IMG_3075.mp4
    ├── IMG_3075.mp4                (4.8 MB)
    └── sidecar.json
```

The API accepts a `template` form parameter. If omitted, it falls back to the `TEMPLATE_DIR` env var default (`base-template-turntable`). Each template is a pre-packaged video + sidecar pair.

### 6.2. Default Template (`basetemplate-turntable`)

A separate directory at the repo root containing a 17MB video + sidecar, used when no template parameter is provided.

### 6.3. Template Resolution Logic (`workspace.py`)

```python
def create_workspace(job_id, template=None):
    templates_root = parent of TEMPLATE_DIR (resolved)
    if template:
        sanitize: reject ".." or "/"
        template_dir = templates_root / template (resolved)
        verify: template_dir starts with templates_root (path traversal check)
    else:
        template_dir = TEMPLATE_DIR
    copy all files to workspace/job_{job_id}/
```

---

## 7. Security

### 7.1. API Authentication
- All endpoints require `X-API-Key` header
- Key configured via `API_KEY` env var
- Validated in middleware (`app/auth.py`)

### 7.2. Rate Limiting
- `/analyze`: 10 requests per minute (slowapi)
- `/status`, `/result`, `/jobs`: 30/minute
- DELETE: 10/minute

### 7.3. Path Traversal Prevention
- Template names are sanitized (no `..` or `/`)
- Resolved template path must remain under `TEMPLATE_DIR` parent
- Uses `Path.resolve()` for canonicalization

### 7.4. Video Validation
- Content-Type check against allowed set: `mp4`, `mov`, `avi`, `mkv`
- File size limit: 500MB

### 7.5. Scanner Block Middleware
FastAPI middleware that returns 404 for:
- Common vulnerability scan paths (`/admin`, `/wp-`, `/phpmyadmin`, `/mysql`, `/backup`, `/config`, `/.env`, `/.git`, `/vendor`, `/shell`, `/cgi-`)
- Scanner user agents (masscan, zgrab, nmap, nikto, sqlmap, acunetix, nessus, openvas)

### 7.6. API Documentation
Disabled by default (`API_DOCS_ENABLED=false`). When disabled, `/docs`, `/redoc`, and `/openapi.json` return 404.

### 7.7. llama-server API Key
- Protected with `Authorization: Bearer <key>` header
- Key stored in Pi's `models.json` (`apiKey` + `authHeader: true`)
- Also passed via `PI_INFERENCE_API_KEY` env var for progress analyzer

---

## 8. Pipeline Performance

### 8.1. Timing Data (2026-05-27 Run)

| Job | Template | Wall Time | Key Stats |
|-----|----------|-----------|-----------|
| T1 | turntable-1 | **19.3 min** (1155s) | ω=7.58 rad/s, r=0.112m, 321 frames, CCW |
| T2 | turntable-2 | **29.0 min** (1739s) | ω=4.94 rad/s, r=0.113m, validation flags: center_mismatch, omega_spike |
| T3 | turntable-3 | **29.2 min** (1754s) | ω=5.70 rad/s, r=0.111m, 350 frames, no_stable_phase_detected |
| **Total** | (sequential) | **76.4 min** (4581s) | |

### 8.2. Historical Data (2026-05-26)

| Job | Template | Wall Time | Notes |
|-----|----------|-----------|-------|
| T1 | turntable-3 | ~35 min | First run |
| T2 | turntable-1 | **33:13** | |
| T3 | turntable-2 | **26:29** | |

Timing variation is primarily driven by Pi iteration/debug cycles (Step 3 ffmpeg escaping, Step 5/7 coordinate center fixes), not by LaTeX compilation.

### 8.3. Bottlenecks
1. **LLM inference latency** — Each Pi step requires multiple LLM calls
2. **Sequential worker** — `concurrency=1` forces queueing; 3 jobs = 3× wall time
3. **Subagent parallel execution** — Subagents run in parallel within Pi but are limited by LLM context window
4. **LaTeX compilation** — Previously had pdflatex timeout loops (solved by latex-document-skill's `compile_latex.sh` with `--use-latexmk`)

---

## 9. LaTeX Integration

### 9.1. latex-document-skill

Cloned from `https://github.com/ndpvt-web/latex-document-skill` into `/home/damar/test-psyh/agent-backend/latex-skill/`. Contains:

- **`scripts/compile_latex.sh`** (26 KB) — Main compilation script; supports auto-engine detection, multi-pass, `--preview` (PNG generation), `--use-latexmk`, `--auto-fix`, error recovery
- **`assets/templates/`** — 28 LaTeX templates (academic, resume, report, presentation, thesis, etc.)
- **`references/`** — 26 reference guides
- **`scripts/`** — 27 utility scripts (PDF merge/encrypt/extract, citation fetch, chart generation, mermaid, graphviz, plantuml, linting, word count, etc.)

### 9.2. Compilation Strategy

The orchestrator prompt (lines 1076, 1096-1101) uses:
```bash
/latex-skill/scripts/compile_latex.sh --preview --use-latexmk <file.tex>
```

This runs automatically when `latexmk` is available (installed via apt in Dockerfile). Without `--use-latexmk`, the script falls back to its own multi-pass logic that detects bibliography, index, and glossary passes.

### 9.3. Latex Compile Subagent

Defined in `.pi/agents/latex-compile-subagent.md` with YAML front matter. This subagent:
- Is invoked by the orchestrator when LaTeX compilation is needed
- References the skill's templates directory for custom class/style imports
- Uses `compile_latex.sh` with appropriate flags
- Falls back to `--engine pdflatex` if `--use-latexmk` fails

---

## 10. Configuration Reference

### 10.1. Environment Variables (.env)

| Variable | Default | Description |
|----------|---------|-------------|
| `API_KEY` | `changeme-random-secret-key-12345` | API authentication key |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection string |
| `PI_MODEL` | `llama.cpp-lab2/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf` | Pi model identifier |
| `TRACKING_API_URL` | `http://192.168.1.13:8086` | SAM tracking API |
| `PI_INFERENCE_URL` | `http://192.168.1.205:8083` | llama.cpp inference server |
| `PI_INFERENCE_API_KEY` | `lazailai` | API key for inference server |
| `TEMPLATE_DIR` | `./templates/base-template-turntable` | Default template path |
| `PROMPT_FILE` | `./prompts/orchestrator.txt` | Pi orchestrator prompt |
| `WORKSPACE_DIR` | `./workspaces` | Workspace storage root |
| `WORKSPACE_TTL_HOURS` | `24` | Workspace cleanup TTL |
| `PI_TIMEOUT_SECONDS` | `5400` | Pi subprocess timeout (90 min) |
| `PI_ANALYZER_TEMPERATURE` | `1.0` | LLM temperature for progress analyzer |
| `PI_ANALYZER_MAX_TOKENS` | `10000` | Max tokens for progress analyzer (needs room after reasoning) |
| `PI_ANALYZER_TIMEOUT` | `90` | HTTP timeout for progress analyzer requests |
| `JOB_STATE_TTL` | `172800` | Redis state TTL (48h) |
| `JOB_RESULT_TTL` | `172800` | Redis result TTL (48h) |
| `API_RATE_LIMIT` | `10/minute` | Rate limit for /analyze |
| `API_DOCS_ENABLED` | `false` | Toggle OpenAPI docs |
| `LATEX_SKILL_PATH` | `/latex-skill` | Mount path for latex-document-skill |

### 10.2. Pi Model Configuration (config/pi-models.json)

```json
{
  "providers": {
    "llama.cpp-lab2": {
      "baseUrl": "http://192.168.1.205:8083",
      "api": "openai-completions",
      "apiKey": "lazailai",
      "authHeader": true,
      "models": [
        {
          "id": "Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf",
          "name": "Qwen 3.6 35B",
          "input": ["text", "image"]
        }
      ]
    }
  }
}
```

---

## 11. Docker Details

### 11.1. Dockerfile

Based on `python:3.12-slim`. Installs:
- **Python packages**: fastapi, uvicorn, celery, redis, pydantic, slowapi, requests, numpy, scipy, opencv, matplotlib, scikit-learn, pandas
- **System packages**: curl, ffmpeg, latexmk, poppler-utils, texlive-science, texlive-latex-extra
- **Node.js 22.19.0**: Official Linux x64 tarball
- **npm packages**: `@earendil-works/pi-coding-agent`, `pi-subagents`
- Copies `config/pi-models.json` to `/root/.pi/agent/models.json`

### 11.2. Image Build Commands

```bash
docker compose build         # Build all services
docker compose up -d         # Start all services (non-production)
docker compose --profile production up -d   # Start with Caddy HTTPS
docker compose down          # Stop all services
docker compose logs -f       # Follow logs
```

### 11.3. Workspace Cleanup

Celery beat runs `worker/cleanup.py` every hour, which:
- Scans `workspaces/` directory
- Checks each job directory's mtime against `WORKSPACE_TTL_HOURS`
- Deletes expired workspaces

---

## 12. Pi (.pi) Configuration

### 12.1. Directory Structure

```
.pi/
├── agent/
│   ├── models.json              — LLM provider/model config
│   ├── prompts/                 — Pi system prompts
│   └── sessions/                — Session files (JSONL)
│       └── --app-workspaces-job_{id}--/
│           └── *.jsonl          (5-6 MB each)
├── agents/                      — Subagent definitions
│   ├── figures-gen-subagent.md
│   ├── question-gen-subagent.md
│   ├── video-annotation-subagent.md
│   ├── latex-compile-subagent.md
│   └── (symlinks to above)
├── extensions/                  — Pi extensions
├── prompts/                     — Additional prompts
└── auth.json                    — Pi auth config
```

### 12.2. Key Detail: `.pi` Symlink in Workspace

Pi looks for `.pi/` relative to its current working directory (CWD). Since the worker spawns Pi inside the job workspace directory, the worker creates a symlink:

```python
pi_config_dst = workspace / ".pi"
pi_config_dst.symlink_to(pi_config_src, target_is_directory=True)  # → /root/.pi
```

This ensures Pi can find `models.json`, subagent definitions, and extension configurations from the workspace CWD.

---

## 13. Session File Architecture

### 13.1. Session File Location

```
~/.pi/agent/sessions/--app-workspaces-job_{job_id}--/
  └── *.jsonl    (5-6 MB for main pipeline, ~9-14 KB for extractor)
```

### 13.2. Session File Format

JSONL (one JSON object per line):
```json
{"message": {"role": "assistant", "content": [...]}}
{"message": {"role": "toolResult", "content": [...]}}
```

The progress analyzer (`app/progress_analyzer.py`):
- Finds the latest JSONL file in the session directory
- Reads the last ~12KB of content (or the whole file if smaller)
- Extracts assistant messages → tool calls → text content
- Sends to LLM for step/progress inference

### 13.3. Bloat Fix History

Originally Pi's stdout was logged (JSONL stream), generating **4.7 GB** of logs per job. The fix: redirect stdout to `DEVNULL` and rely solely on Pi's internal session file (~400 KB–6 MB) for progress analysis. This eliminated the disk I/O bottleneck and log rotation concerns.

---

## 14. Validation Flags & Quality Metrics

The pipeline outputs validation flags to indicate data quality issues:

| Flag | Meaning |
|------|---------|
| `center_mismatch` | Calibration center differs from fitted center |
| `center_switched_to_fit` | System overrode calibration center with RANSAC fit |
| `fft_skipped_insufficient_data` | Not enough frames for FFT period detection |
| `omega_spike` | Detected anomalous angular velocity values |
| `physical_size_estimated` | Physical size was estimated from world knowledge, not measured |
| `no_stable_phase_detected` | No period of steady rotation found |

---

## 15. Known Issues & Edge Cases

1. **J3 file paths with `../../`** — The job output extractor can return relative paths (e.g., `../../analysis_output/report/student_edition.pdf`) that get collapsed into incorrect URLs when prepended with `/files/job_XXX/`. The actual files exist correctly; this is a cosmetic URL issue.

2. **Qwen3 thinking mode token consumption** — The model's `reasoning_content` field consumes token budget. `max_tokens` must be set high enough (10000) to ensure the actual response appears in `content`.

3. **Subagent trace visibility** — Subagent intermediate reasoning is embedded in the main session file's large JSONL response lines but not stored separately. Debugging subagents requires parsing the main session file.

4. **No SSL on dev** — Only Caddy (production profile) provides HTTPS. The socat tunnel on port 8082 exposes plain HTTP.

5. **Gateway blocks inbound** — Upstream router 140.115.126.254 blocks inbound traffic; the socat tunnel on public IP works because the UFW on lab1 explicitly allows it.

6. **Pi timeout vs pipeline completion** — `PI_TIMEOUT_SECONDS=5400` (90 min) covers the worst case, but typical runs are 19–35 min. A failed timeout kills the subprocess and marks the job as failed.

---

## 16. Pipeline Output Structure

After successful completion, each job workspace contains:

```
workspaces/job_{id}/
├── input_video.mp4
├── sidecar.json
├── .pi -> /root/.pi/
├── analysis_output/
│   ├── data/
│   │   └── stats.json               — Full kinematics data
│   ├── roi/
│   │   └── cropped.mp4              — Cropped region of interest
│   ├── tracking/
│   │   └── ...                      — Raw tracking data
│   ├── plots/
│   │   ├── trajectory.png           — 2D trajectory plot
│   │   ├── radius_t.png             — Radius vs time
│   │   ├── omega_t.png              — Angular velocity vs time
│   │   ├── theta_t.png              — Angle vs time
│   │   ├── ac_t.png                 — Centripetal acceleration vs time
│   │   ├── summary_panel.png        — Multi-panel summary
│   │   ├── annotated_image.png      — Frame with overlay
│   │   └── annotated_table.png      — Data table
│   ├── report/
│   │   ├── student_edition.pdf      — Student worksheet
│   │   ├── teacher_key.pdf          — Teacher answer key
│   │   └── report.md                — Summary report
│   └── video_annotation/
│       └── annotated_video.mp4      — Video with overlays
├── step1..step8                     — Individual step scripts
├── step1_output..step8_output       — Step outputs
└── ... (other intermediate files)
```

---

## 17. File Reference (Source Code)

| File | Lines | Purpose |
|------|-------|---------|
| `app/main.py` | 48 | FastAPI app creation, middleware, static mount |
| `app/routes.py` | 116 | All API endpoints |
| `app/schemas.py` | 40 | Pydantic request/response models |
| `app/auth.py` | 8 | API key authentication |
| `app/job_store.py` | 80 | Redis CRUD for job state/result |
| `app/workspace.py` | 43 | Workspace creation, video/sidecar drop, deletion |
| `app/progress_analyzer.py` | 107 | Pi session file analysis via LLM |
| `app/limiter.py` | 7 | SlowAPI rate limiter config |
| `worker/celery_app.py` | 30 | Celery app with Redis broker |
| `worker/tasks.py` | 155 | Pi subprocess management, progress polling, extractor |
| `worker/cleanup.py` | 30 | Periodic workspace cleanup |
| `prompts/orchestrator.txt` | 1174 | Full Pi pipeline definition |
| `prompts/job-output-extractor.txt` | 80 | Pi output file scanner prompt |
| `config/pi-models.json` | 16 | Llama.cpp provider + model config |
| `docs/tunneling.md` | 148 | Socat tunnel documentation |
| `Dockerfile` | 28 | Container build instructions |
| `docker-compose.yml` | 103 | Multi-service orchestration |
| `Caddyfile` | 3 | Caddy reverse proxy config |
| `requirements.txt` | 13 | Python dependencies |
| `.env` | 21 | Environment variables |

---

## 18. Development & Operations

### 18.1. Local Development

```bash
# Build and start with live reload
docker compose build api      # Rebuild API only
docker compose up -d          # Start all services
docker compose logs -f worker # Follow worker logs
docker compose restart worker # Restart worker after code changes
```

The API and worker mount their source directories as volumes, so Python changes take effect immediately (except for imports that need process restart).

### 18.2. Checking Sessions

```bash
# Find session files for a job
ls -la ~/.pi/agent/sessions/--app-workspaces-job_{id}--/

# Check main session file size
wc -c ~/.pi/agent/sessions/--app-workspaces-job_{id}--/*.jsonl

# Progress analysis debugging
export PI_ANALYZER_TEMPERATURE=0.7
```

### 18.3. Common Operations

```bash
# List all jobs
curl http://localhost:8000/jobs -H 'X-API-Key: ...'

# Cancel/delete a job
curl -X DELETE http://localhost:8000/job/{job_id} -H 'X-API-Key: ...'

# Get full results
curl http://localhost:8000/result/{job_id} -H 'X-API-Key: ...'

# Download output file
curl -O http://localhost:8000/files/job_{id}/analysis_output/report/student_edition.pdf

# Clean all completed workspaces
rm -rf workspaces/job_*
```

### 18.4. Restarting After System Reboot

```bash
# Docker containers (auto-restart not configured)
docker compose up -d

# Socat tunnels (systemd, enabled)
sudo systemctl restart socat-proxy
sudo systemctl restart socat-llama

# Check tunnels
sudo systemctl status socat-proxy
sudo netstat -tlnp | grep socat
```

---

## Appendix A: LaTeX Skill Commands

The latex-document-skill provides these utilities in `latex-skill/scripts/`:

| Script | Purpose |
|--------|---------|
| `compile_latex.sh` | Compile .tex to PDF (auto engine, multi-pass, latexmk) |
| `latex_lint.sh` | Check LaTeX for common errors |
| `latex_analyze.sh` | Analyze document statistics |
| `latex_wordcount.sh` | Count words in .tex files |
| `latex_diff.sh` | Show differences between two .tex files |
| `pdf_merge.sh` | Merge multiple PDFs |
| `pdf_encrypt.sh` | Password-protect PDF |
| `pdf_optimize.sh` | Compress PDF for web |
| `fetch_bibtex.sh` | Fetch BibTeX from DOI |
| `generate_chart.py` | Generate charts for inclusion in LaTeX |

---

## Appendix B: Sample stats.json

```json
{
  "object_name": "red phone",
  "mean_r_m": 0.112,
  "std_r_m": 0.0024,
  "mean_omega": 7.51,
  "std_omega": 2.77,
  "stable_mean_omega": 7.58,
  "mean_ac": 7.17,
  "max_ac": 17.29,
  "period_s": 0.83,
  "frequency_hz": 1.21,
  "rotation_direction": "CCW",
  "px_per_m": 3498.3,
  "center_source": "ransac_fit",
  "tracking_coverage_pct": 100.0,
  "n_valid_frames": 321,
  "active_duration_s": 2.14,
  "validation_flags": []
}
```

---

## Appendix C: Docker Health & Diagnostics

```bash
# Check all container health
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Redis operations
docker exec agent-backend-redis-1 redis-cli KEYS 'job:*'
docker exec agent-backend-redis-1 redis-cli GET 'job:{id}:state'

# Worker queue depth
docker exec agent-backend-redis-1 redis-cli LLEN celery

# Clean Redis entirely (CAUTION: loses all job state)
docker exec agent-backend-redis-1 redis-cli FLUSHALL
```

---

*Report generated 2026-05-28. System designed for turntable centripetal motion analysis education.*
