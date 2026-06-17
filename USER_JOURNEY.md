# Centri — User Journey

_Last updated: 2026-06-04_

The path a learner walks from "I have a phone and something spinning" to "I
understand centripetal acceleration." Each stage lists **what the learner does**,
**what they see**, and **what happens behind the scenes** (which service does the
work). Written from the learner's point of view; the product never shows raw
commands or jargon.

> The whole loop runs from the phone over the LAN. App = `~/centri/app`,
> measurement = `agent-backend` (`:8088`), tutor = `pedagogy-backend` (`:8090`),
> tracking = SAM3 (`:8086`).

---

## At a glance

```
consent ─► home ─►(first run) briefing ─► record / upload ─► annotate ─►
   live progress ─► results ─► tutor ─► (back to home / history)
                                  └─────────── feedback (HITL) ──────────┘
```

A single learner-facing thread; every box is one screen.

---

## 1. Consent — "what this app does with your video"

- **Does:** taps through a one-time consent screen.
- **Sees:** a plain-language note on what's captured (a short video, no account)
  and a telemetry opt-out.
- **Behind the scenes:** gated once in `main.dart`; the choice sets whether
  implicit setup telemetry is sent later. No login, no Firebase — just a local
  `user_id`. This is the deliberate departure from the old `G-Uphysic` auth flow.

## 2. Home — "start a new experiment"

- **Does:** lands on the home screen; starts a new analysis or opens a past one.
- **Sees:** a clean entry point plus **history** of previous experiments
  (done / running / failed — all openable).
- **Behind the scenes:** history is the list of prior jobs; nothing runs yet.

## 3. Briefing (first run) — "read before you do"

- **Does:** reads a short primer on circular motion, then continues (skippable).
- **Sees:** a phyphox-style "read before you measure" card — the pedagogy starts
  *before* the data does.
- **Behind the scenes:** purely client-side framing; sets the learner up to
  predict before they measure.

## 4. Record / upload — "film something spinning"

- **Does:** records a fan, turntable, ball-on-string… or picks an existing clip.
- **Sees:** a normal capture/upload screen with a thumbnail of their clip.
- **Behind the scenes:** the app holds the video locally; a thumbnail is
  generated (the `video_thumbnail` package — the one with the pub-cache patch).

## 5. Annotate — "tell us what's spinning" (assisted)

This is the key human-in-the-loop step: **app proposes, learner confirms.**

- **Does:** confirms or adjusts the moving object, a reference object of known
  size, and **marks the rotation centre**.
- **Sees:** faint suggestion boxes already drawn for them; a "check with SAM3"
  action that snaps the boxes tight; gentle flags when a label doesn't ground.
- **Behind the scenes:**
  - `agent-backend /suggest-scene` makes **one VLM frame call** → pre-fills the
    moving object, reference, size in cm, and a rotation-centre guess.
  - `agent-backend /verify-objects` proxies **SAM3 `/segment`** (~2s) → tight
    boxes; the app never touches the GPU box directly.
  - The **user-marked centre is authoritative** — sent as a frame fraction
    (`rotation_center_frac`), decoupled from the reference object, which is used
    for **scale only**.
  - Both LLM/SAM calls are offloaded to a threadpool so the API stays responsive.

## 6. Live progress — "watch it think"

- **Does:** waits, but with visibility — not a spinner.
- **Sees:** clean, ordered, **education-language stages** the agent self-reports
  ("finding the object", "tracking its motion", "measuring", "writing it up"),
  not a loading bar and never raw logs.
- **Behind the scenes:**
  - `POST /analyze` (video + sidecar) enqueues a Celery job; the **`pi` agent**
    runs `prompts/orchestrator.txt` inside the worker container:
    ffprobe → ROI crop → **SAM3 tracking** → trajectory (RANSAC) → calibration →
    kinematics → annotated video + plots → questions → reports.
  - **Coverage gate:** SAM3 is non-deterministic, so tracking is wrapped in a
    check — accept ≥85%, retry up to 3× keeping the best, **abort below 50%**
    rather than emit garbage physics (with a `/reset` to the tracker between
    tries). The learner just sees an honest retry, not a bad result.

## 7. Results — "here's the real physics, from your video"

- **Does:** explores their own measurement and the worked worksheet.
- **Sees:** **native, data-driven** results — `fl_chart` graphs (ω / aᶜ /
  trajectory), measurement cards (radius, ω, aᶜ, period), and a
  **student/teacher worksheet** with answers + worked solutions, formulas
  rendered as **LaTeX**. The only baked artifact is the annotated video — no
  summary PNG, no PDF.
- **Behind the scenes:** the app reads a structured `GET /result`
  (`series` for the charts + `worksheet` for the questions/solutions) and renders
  it natively. `stats.json` / `kinematics.csv` are the durable outputs;
  `kinematics.csv` is **the seam** to the tutor.

## 8. Tutor — "now let's reason about it" (Socratic)

- **Does:** answers guiding questions about their *own* object and *own* data.
- **Sees:** a staged, non-revealing dialogue:
  1. **problem-finding** — spot circular motion around you.
  2. **problem-exploring stage 1** — reason about the object (KG-grounded).
  3. **problem-exploring stage 2** — reason about *their* measured numbers
     (radius, ω, aᶜ, period).
  4. **problem-generating** — author/solve a problem from their data.
  - Each answer returns **brief feedback that doesn't give it away**, a next step,
    and quietly records any misconception.
- **Behind the scenes:**
  - `pedagogy-backend /inquiry/*`, grounded in the centripetal-acceleration
    knowledge graph + bilingual (EN/ID) few-shot examples.
  - Stage 2 auto-fetches the measurement via
    `/inquiry/generate/problem-exploring-stage-2/from-job/{job_id}` — the
    `MeasurementContext` seam in action.
  - A **student model** (ability band + misconception history) personalises the
    difficulty; prompts emit inline LaTeX the app renders.

## 9. Feedback (HITL) — "was this right?"

- **Does:** optionally flags what was wrong (role-tagged) from the results screen.
- **Sees:** a light feedback affordance, not a survey.
- **Behind the scenes:** `agent-backend /feedback` appends to JSONL that outlives
  the 24h workspace TTL. Two event types: implicit `setup_correction`
  (VLM-predicted vs SAM-verified vs final, gated on telemetry opt-in) and explicit
  `result_feedback`. This is the data that improves the assisted-annotation guesses.

---

## What the learner never sees

By design, and in contrast to the old prototype:

- No login / register / account — just a local `user_id`.
- No raw commands, logs, or agent chatter — only education-language stages.
- No phyphox sensor toolbox (gyroscope/accelerometer/audio/Bluetooth) — Centri is
  **video-for-sensor**, focused on the one circular-motion experiment.
- No separate question-bank — practice questions arrive **with** the measurement.

## Where it can wobble (honest)

- The shared **Qwen inference server** (`192.168.1.205:8083`, not ours) can crash
  under load — affects suggest + tutor.
- **Shared-GPU contention** — interactive calls can starve during a long analysis.
- **SAM3 lifetime leak** — auto-recycled; the coverage gate keeps bad runs from
  reaching the learner.
- **Measurement consistency** — ω / active-window can vary run-to-run on the same
  clip.
```
