# Centri

Measure real circular-motion physics from a phone video, then tutor the student through it — a video-for-sensor rebuild of the phyphox circular-motion experiment.

A learner records something spinning, marks the moving object + a scale reference + the rotation centre, and Centri tracks it frame-by-frame, computes the kinematics (ω, aᶜ, period, radius), and renders the results + a Socratic inquiry tutor natively in the app.

## Repository layout

```
~/centri/
  app/               Flutter app (Android) — the product UI
  agent-backend/     Measurement backend — FastAPI + Celery + the `pi` agent, runs in Docker
  pedagogy-backend/  Tutor backend — FastAPI, staged Socratic inquiry + question generation
  sam3 → ~/sams2/sam3cpp   Object tracking server (C++/CUDA). SYMLINK — see note below.
  archive/           Superseded code (old fastapi-gpt pedagogy variant)
```

> **Why `sam3` is a symlink:** the SAM3 tracker is a 6.8 GB compiled C++/CUDA project with an absolute RPATH baked into its binary and 4.8 GB of `.ggml` models, embedded in a larger research dir (`~/sams2`). Moving it would break library/model loading (recompile needed), so it stays in place and is symlinked into `~/centri/` for navigation.

> **Not in this folder:** `~/G-Uphysic` — the older native-Android (phyphox-derived) app. Left in place because it's a separate git repo and was the active working directory; relocate it from a fresh shell if desired.

## Architecture

```
                       ┌─────────────────────── phone (LAN) ───────────────────────┐
                       │                                                            │
   pick video → annotate (mark object / ruler / centre)                  tutor (Socratic)
                       │                                                            │
              POST /suggest-scene  ──┐                                              │
              POST /verify-objects ──┤                                              │
              POST /analyze ─────────┤                                     POST /inquiry/*
                       ▼             │                                              ▼
        agent-backend  api (8088) ───┤                                  pedagogy-backend (8090)
              │  └─ enqueue ─► redis (internal) ─► worker [pi agent]              │
              │                                        │                          │
              │                       ┌────────────────┴───────────┐              │
              ▼                       ▼                            ▼               ▼
        SAM3 /track (8086)     inference /v1 (.205:8083, Qwen)   ... ◄────────────┘
        object tracking        reasoning + vision + tutor LLM
```

- The **app talks only to the two backends** (8088 measurement, 8090 tutor). Each backend fans out to SAM3 + the shared Qwen inference server.
- **`pi`** (the coding agent) orchestrates the measurement pipeline inside the worker container: ffprobe → ROI crop → SAM3 tracking → trajectory → kinematics → plots/annotated video → questions.

## Services & ports (host `192.168.1.13`)

| Service | Port | How to start | Notes |
|---|---|---|---|
| agent-backend (api+worker+redis) | **8088** | `cd ~/centri/agent-backend && docker compose up -d redis api worker` | pi runs in the worker container |
| pedagogy-backend | **8090** | `cd ~/centri/pedagogy-backend && uvicorn main:app --host 192.168.1.13 --port 8090` (env `sam3`) | needs `.env` (Qwen URL+key) |
| SAM3 tracker | **8086** | `~/centri/sam3/run_sam3.sh` (supervisor, auto-restarts) | self-heals via `POST /reset` |
| Inference (Qwen) | **8083** | external box `192.168.1.205` | **not ours** — shared GPU; has gone down under load |

The app's `defaultMeasurementUrl`/`defaultPedagogyUrl` point at `192.168.1.13:8088`/`:8090`. **ufw** must allow those ports from the LAN:
```
sudo ufw allow from 192.168.1.0/24 to any port 8088 proto tcp
sudo ufw allow from 192.168.1.0/24 to any port 8090 proto tcp
```

## Current state (verified)

- ✅ Full measurement pipeline end-to-end **from the phone**, in Docker → annotated video + native charts + worksheet.
- ✅ Auto-guess (VLM `/suggest-scene` + SAM3 `/verify-objects`); user-marked rotation centre is authoritative.
- ✅ Live progress feed (agent self-reports clean, ordered, education-language stages).
- ✅ Tracking **coverage gate** with bounded retry + SAM3 self-recycle (SAM3 degrades over its lifetime).
- ✅ Native Results UI (fl_chart graphs, native worksheet with student/teacher toggle, LaTeX rendering) — no PNG/PDF.
- ✅ Socratic tutor (staged inquiry → generated problem) with LaTeX.

## Known issues / watch-items

- **Inference (`.205:8083`) instability** — has crashed under load several times; when it does, the model unloads (rpc worker drops ~22.9 GB → ~960 MB). Restart it on the `.205` box.
- **Shared-GPU contention** — interactive calls (auto-suggest, tutor) starve while a long analysis job runs; both use the one Qwen server.
- **SAM3 lifetime leak** — coverage decays over many `/track` calls; the gate auto-recycles via `/reset` (proper fix: per-call memory release in `sam3_api_worker_hybrid`). See `docs` in each backend.
- **`video_thumbnail` pub-cache hack** — `app/` Android build needs a manual patch to `~/.pub-cache/.../video_thumbnail-0.5.6/android/build.gradle` that `flutter pub get` reverts.
- **USB to the Nokia is flaky** — `flutter run` repeatedly "Lost connection"; builds still install. Use a different cable or `adb tcpip`.

See each component's `README.md` (and `agent-backend/docs/`) for details.
