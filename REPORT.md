# Centri — Project Report

_Last updated: 2026-06-04_

## Quick update

Centri is a **video-for-sensor** rebuild of phyphox's circular-motion learning experiment: a learner films something spinning, and the app measures the real physics (ω, aᶜ, period, radius) and tutors them through it — replacing phyphox's gyroscope modality with computer vision.

It is now a working **standalone product** (Flutter app + two backends + a tracking server), rebuilt out of the older native-Android prototype (`G-Uphysic`, a phyphox fork). As of this update the **full loop runs end-to-end from the phone**: record → annotate → measure → native results → Socratic tutor. Everything is consolidated under `~/centri/` and running on the LAN host `192.168.1.13`.

**Status by piece:** app ✅ live on device · measurement backend ✅ (Dockerized, self-healing) · pedagogy backend ✅ · tracking server ✅. The main external risk is the shared **Qwen inference server** (`192.168.1.205:8083`), which is not ours and has crashed under load several times.

---

## Centri app (Flutter) — `~/centri/app`

A clean, standalone Flutter app (`com.centri.centri_app`, Material 3) that rebuilds the *learning flow* from the `G-Uphysic` native app as a focused product — not the whole phyphox toolbox.

### Implemented (ported/rebuilt from G-Uphysic)
G-Uphysic was a phyphox fork with a learning layer bolted on (login/auth, `PiAnalysisActivity`, `ExperimentInquiryActivity`, question-gen, history, Firebase). The Flutter app reimplements the **learning-flow subset** that matters, cleanly:

- **Video analysis flow** (was `PiAnalysisActivity` → `analyze`/`status`/`result`/`jobs`): consent → home → upload/record → annotate → live progress → results.
- **Socratic inquiry tutor** (was `ExperimentInquiryActivity` + `InquiryFeedbackActivity` → `inquiry/*`): 4-stage guided inquiry (problem-finding → exploring 1/2 → problem-generating) + response feedback.
- **History** of past analyses; **feedback** (HITL) capture.

### Not carried over (intentionally)
The broad phyphox sensor toolbox (gyroscope/accelerometer experiments, audio, Bluetooth), **login/register/auth + Firebase**, and the standalone question-bank activities. The app uses a simple `user_id` instead of accounts; practice questions now come *with* the measurement result rather than a separate generator.

### New beyond G-Uphysic (built this cycle)
- **Pre-read briefing** (phyphox-style "read before you do") shown first-run, with skip.
- **Assisted annotation** — VLM proposes object/reference/centre + SAM3 verifies; the **user-marked rotation centre is authoritative** (sent as a frame fraction, decoupled from the scale reference).
- **Live agentic progress** — the agent self-reports clean, ordered, education-language stages (not a single loading bar).
- **Native, data-driven Results** — `fl_chart` graphs (ω/aᶜ/trajectory), native measurement cards, a **student/teacher worksheet** with answers + worked solutions, and **LaTeX rendering** of formulas. The only baked artifact is the annotated video; no summary-panel PNG or PDFs.
- Open any job (done/running/failed) from history.

Toolchain notes: Flutter at `/opt/flutter` (invoke `env FLUTTER_ROOT=/opt/flutter …`); the `video_thumbnail` package needs a manual pub-cache patch that `pub get` reverts.

---

## centri-be — measurement backend (`~/centri/agent-backend`)

The video→physics pipeline. FastAPI + Celery + the **`pi`** coding agent, running in **Docker** (api + worker + redis); `pi` orchestrates the CV pipeline inside the worker container.

- **Flow:** `/analyze` (video + sidecar) → enqueue → worker runs `pi` on `prompts/orchestrator.txt`: ffprobe → ROI crop → **SAM3 tracking** → trajectory (RANSAC) → calibration → kinematics → annotated video + plots + questions → student/teacher reports.
- **Outputs:** `stats.json`, `kinematics.csv` (the seam to pedagogy), annotated video, and a **structured `/result`** (`series` for charts + `worksheet` with answers/solutions) so the app renders natively.
- **Assisted-annotation endpoints:** `/suggest-scene` (one VLM frame call) + `/verify-objects` (proxies SAM3 `/segment`); both offloaded to a threadpool so the blocking LLM/SAM calls don't freeze the event loop.
- **Robustness added this cycle:**
  - **Tracking-coverage gate** — SAM3 is non-deterministic, so `/track` is wrapped in a coverage check: accept ≥85%, else retry (≤3) keeping the best; **abort below 50%** rather than emit garbage physics.
  - **User-centre authority** — consumes `rotation_center_frac`; the reference object is used for scale only.
  - **Live progress feed** + the agent's own per-step progress reports.
- Bind-mounted code (edits take effect on container restart; `orchestrator.txt` is read per-job).

---

## pedagogy-be — tutor backend (`~/centri/pedagogy-backend`)

Our own pedagogy service (Phase 1), separate from measurement, joined by the `kinematics.csv` seam and sharing the Qwen inference server. FastAPI on **`:8090`**.

- **Staged Socratic inquiry:** `/inquiry/generate/problem-finding → problem-exploring-stage-1 → -stage-2 → problem-generating`, plus `/inquiry/submit-response` (feedback without revealing the answer, misconception detection).
- **Tiered question generation** (`/questions/generate`) and a **student model** (`/students/profile` — ability band + misconception history), with KG + few-shot grounding and EN/ID bilingual support.
- **LaTeX** — prompts now emit formulas as inline LaTeX (`$…$`, JSON-safe), rendered natively in the tutor.
- Verified live against Qwen end-to-end (generates real inquiries + solvable problems with worked solutions).
- This **supersedes** the older `fastapi-gpt` variant (now in `archive/`).

---

## Overall

- **End-to-end works from the phone**, all services consolidated under `~/centri/` and healthy (`8086` SAM3, `8088` measurement, `8090` pedagogy).
- **What's solid:** the measurement pipeline, the native results UX, assisted annotation, the tutor, and the self-healing around SAM3's quirks.
- **Open risks / next:** (1) **inference stability** — the shared Qwen box crashes under load; (2) **shared-GPU contention** — interactive calls (suggest/tutor) starve during a long analysis job; (3) **SAM3 lifetime leak** — auto-recycled for now, proper fix is per-call memory release; (4) **measurement consistency** — angular-velocity/active-window estimate can vary run-to-run on the same clip; (5) the native-Android `G-Uphysic` app remains separate (not folded into `~/centri/`).
- See `README.md` (architecture, ports, how to run) and `AGENTS.md` (working conventions + gotchas).
