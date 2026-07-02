# Architecture Overview — Cross-System

> How the three systems fit together, who owns what, the deployment topology, the
> modality-substitution plan, the phase roadmap, and the accuracy pilot. Companions:
> [data-contract.md](data-contract.md), [pipeline-internals.md](pipeline-internals.md),
> [change-spec-phase0.md](change-spec-phase0.md).

## 1. The three systems

| System | Repo | Role | Ownership |
|---|---|---|---|
| **Measurement** | `agent-backend` | video → physics (+ static worksheet/PDF) | **ours** (code + infra) |
| **Pedagogy** | `fastapi-gpt` (branch `development`) | physics → interactive, personalized inquiry | hers; high-value assets are **portable** |
| **App** | phyphox fork (Android, Java) | capture / annotate / display | hers/husband's → **being rewritten in Flutter (ours)** |

Today's app talks to **both** backends: the Pi/video endpoints (`/analyze`,
`/status`, `/result`, `/jobs`) hit `agent-backend`; the inquiry/question endpoints
(`/inquiry/...`, `/easy-question`, `/validate-object-centripetal/`, `/calculate-radius-auto`)
hit `fastapi-gpt`.

**Note on `fastapi-gpt` versions:** the simple 3-endpoint code on its `main` branch is
v1. The real system is on **`origin/development`** — `router_inquiry.py` (~2,456 lines:
staged problem-finding → problem-exploring 1 → 2, with feedback/scaffolding/non-reveal
hints), `inquiry_db.py` (MySQL `student_profile` with IQ→ability band, +
`misconception_history`), a centripetal-acceleration **knowledge graph**, and curated
few-shot **testsets** (bilingual EN/ID). The portable IP = knowledge graph + testsets +
prompt templates + ability/misconception logic.

## 2. Deployment topology (we own all of it)

From `REPORT.md §2, §5`:

```
            Internet (public IP 140.115.126.111, NCU / lab)
                         │  socat tunnels (systemd on lab1, 10.0.0.1)
                         ▼
   lab2 (10.0.0.2) — Docker Compose:
     ├── api     (FastAPI :8000)          ← endpoints
     ├── worker  (Celery, concurrency=1)  ← runs `pi` orchestrator, 1 job at a time
     ├── beat    (Celery beat)            ← hourly workspace cleanup (TTL 720h / 30 days)
     ├── redis   (job state/result + broker; result TTL 48h; AOF persistent, named volume)
     └── caddy   (prod-only HTTPS)
                         │
        ┌────────────────┴───────────────────┐
        ▼                                     ▼
  Tracking API (SAM 3 CPP)            Inference (llama.cpp)
  192.168.1.13:8086                   192.168.1.205:8083
  point tracking, 1 call/job          Qwen3.6-35B-A3B (4-bit)
```

Redis keys: `job:{id}:state` (`status/step/progress_pct/message/started_at`) and
`job:{id}:result` (`stats` + `files`). The gateway `140.115.126.254` blocks inbound;
the tunnel works because lab1's UFW explicitly allows it.

**Independence:** because we own the GPU, the SAM 3 tracker, the Qwen server, the
pipeline code, *and* (soon) a ported pedagogy backend + a Flutter app, the residual
dependency on supervisor/husband approaches zero once Phases 1–2 land.

## 3. The seam (one table, one CSV)

The boundary between *measurement* and *pedagogy* is a single per-frame CSV. Her
endpoints already read `Time (s), Angular velocity (rad/s), Acceleration (m/s^2)`; our
`kinematics.csv` carries the same quantities as `time_s, omega_rad_s, ac_m_s2`. Emit
those three columns under her headers and video output is a **drop-in** for her
pedagogy — full mapping in [data-contract.md §5](data-contract.md).

## 4. Modality substitution — what the prof asked for

**Goal:** replace the *sensor* modality with *video*, and improve. Reframed precisely:
make the video pipeline emit the same physics the sensor produced, so everything
downstream (her tutor) works unchanged.

**The improvement falls out of her own architecture.** Her stack splits capture into
two acts: an **image** (`/process-image/` → object label + center + radius, stage 1) and
the **sensor** (gyroscope time-series, stage 2). **One video gives us all of it at once**
— object + radius (from tracking + reference scaling) *and* the ω/aᶜ time-series. So
video doesn't just substitute the sensor leg; it *collapses her two captures into one*.
That is the genuine "improve even further."

## 5. Phase roadmap

| Phase | What | Risk it removes | Size |
|---|---|---|---|
| **0** | Expose `kinematics.csv` via the API (+ her-schema CSV); run the pilot | proves video accuracy (the core thesis) | small — see [change-spec-phase0.md](change-spec-phase0.md) |
| **1** | Stand up our own pedagogy backend; port her knowledge graph + testsets + prompts + ability/misconception logic; feed it from our series | owns the tutor; runs on video data | the biggest *build* |
| **2** | Flutter app — thin client over both backends (capture+annotate → measurement → staged inquiry UI) | replaces the Java app; cross-platform | medium, deferrable (contracts frozen first) |
| **3** | Improvements + Bahasa translation layer (her testsets are already ID); collapse the two captures into one video | differentiation | ongoing |

Ordering principle: **by risk, not by layer.** Measurement is upstream of everything and
is the existential unknown; the app is the lowest-risk, most-deferrable piece.

## 6. Accuracy pilot (video vs sensor)

**Question:** is video accurate enough to replace the gyroscope? (And *where* does it
win/lose — informing substitution vs coexistence.)

**Design (recommended first pass):**
- **Sensor leg:** stock phyphox gyroscope export (no dependency on her husband). Same
  underlying quantity; cleaner reference than her processed pipeline.
- **Video leg:** this pipeline → `kinematics.csv` (her-schema columns).
- **Ground truth:** a constant-RPM source (turntable / record player at 33⅓ / small
  motor) → *absolute* accuracy for both methods, not just mutual agreement.
- **Matching:** manual trial IDs (write on a card visible in frame; name the sensor CSV
  by trial). No code coupling — compare offline in a notebook.

**Comparison depth:**
- *Summary stats first* (mean ω, period, revolutions over the same spin) — needs only
  trial-ID matching, no clock sync; answers "good enough?".
- *Time-series later* (ω(t) during spin-up/down) — align by **cross-correlation**
  (robust to phone-clock drift), not wall-clock timestamps.

A full CSV/DB export from her side is the *ideal* interface (fully decoupled), not a
worst case — but the pilot does not require it.

> **Automated regression:** `tools/gt_harness.py` already does the summary-stats
> comparison against phone-gyro CSVs in `/home/damar/new-case/` (developer-only ground
> truth — never seeded to a workspace, never seen by the agent). On IMG_3075 the
> tracking-only pipeline matches the gyro mean ω to **0.3%**.

## 7. Determinism: the seeded frozen pipeline

The kinematics (old orchestrator Steps 5–8) is **not** authored by the LLM. It lives in
[`workspace_lib/analysis/`](../workspace_lib/analysis/README.md) and is **seeded into
every job workspace** by `app/workspace.py::seed_pipeline` — the same mechanism that
drops `sidecar.json` and the template video. The orchestrator's perception steps write
`pipeline_inputs.json`; Step 6 runs `python -m analysis.run`. This guarantees "same
inputs → byte-identical `stats.json`", fixing the 28-schema / invalid-NaN /
drift-8.9→1013 variance the agent-authored version exhibited. Full behaviour map:
[agents-behaviour.md](agents-behaviour.md).
