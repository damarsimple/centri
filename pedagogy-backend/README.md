# Centri Pedagogy Backend

Our own pedagogy service for the video-based circular-motion learning product — the
**interactive, adaptive inquiry tutor** (Phase 1). Separate from the measurement
pipeline (`agent-backend`), joined to it by the `kinematics.csv` seam, and sharing the
same Qwen llama.cpp infra.

> Context & plan: `../agent-backend/docs/architecture-overview.md`.

## What it does

A staged Socratic tutor for centripetal acceleration, grounded in a knowledge graph
and few-shot examples, that adapts to a student model:

- **Stage 1 — object inquiry**: the student points at a real object (fan, turntable,
  ball-on-string…); the tutor asks a guiding question grounded in that object's KG facts.
- **Stage 2 — data inquiry**: fed the physics measured from the student's own video
  (radius, ω, aᶜ, period), the tutor asks about the relationships in *their* data.
- **submit-response**: evaluates the answer, returns brief **non-revealing** feedback +
  a next step, and records any detected misconception.
- **Student model**: ability band (from IQ rank → easy/intermediate/advanced difficulty)
  + per-student misconception history, used to personalize subsequent inquiry.

This is the *adaptive* tutor — distinct from `agent-backend`'s static 8-question PDF
worksheet. They are complementary.

## Ported assets (from `fastapi-gpt` `origin/development`)

- `data/knowledge_graphs/centripetal_acceleration.json` — core concepts, formulas,
  objects map, graph patterns, stage/difficulty rules, misconceptions-by-stage.
- `data/testsets/problem_exploring_stage{1,2}.jsonl` — bilingual (EN/ID) few-shot
  inquiry dialogues.

The serving code is our own clean rebuild (not her 2,456-line router).

## Layout

```
main.py                 FastAPI app (port 8090)
app/
  config.py             env-driven settings (LLM, data paths, DB)
  db.py                 shared sqlite access + schema registry
  llm.py                OpenAI-compatible client → Qwen llama.cpp
  jsonutil.py           robust JSON extraction from LLM replies
  knowledge.py          knowledge-graph access + prompt grounding
  misconceptions.py     canonical misconception taxonomy (validated ids)
  scoring.py            deterministic concept-coverage signal (EN+ID)
  student_model.py      student_profile + misconception_history (+ ability band)
  inquiry_store.py      persisted inquiries + responses (session log)
  measurement.py        agent-backend /result → MeasurementContext (the seam)
  students.py           /students/* profile + misconception endpoints
  questions.py          /questions/* tiered question generation
  inquiry/
    schemas.py          request/response models (incl. MeasurementContext = the seam)
    testsets.py         few-shot loaders
    prompts.py          staged-inquiry prompt builders (KG + few-shot grounded)
    router.py           /inquiry/* endpoints
data/                   ported KG + testsets
tests/                  pytest core-logic tests (no network)
```

## The seam

`inquiry.schemas.MeasurementContext` is filled from `agent-backend`'s output:
`{ object_label, radius_m, mean_omega_rad_s, mean_ac_m_s2, period_s }` ←
`stats.json` / `kinematics.csv`. See `../agent-backend/docs/data-contract.md`.

## Run

```bash
cd ~/centri/pedagogy-backend
cp .env.example .env            # set PEDAGOGY_LLM_URL + PEDAGOGY_LLM_KEY (shared Qwen)
# uses the shared `sam3` conda env (fastapi/uvicorn already installed)
~/miniconda3/envs/sam3/bin/python -m uvicorn main:app --host 192.168.1.13 --port 8090
# bind the LAN IP, not 0.0.0.0; ufw must allow 8090 from 192.168.1.0/24 for the phone.
# docs at http://192.168.1.13:8090/docs
```

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | liveness |
| POST | `/inquiry/generate/problem-finding` | prompt student to spot circular motion around them |
| POST | `/inquiry/generate/problem-exploring-stage-1` | object-based inquiry |
| POST | `/inquiry/generate/problem-exploring-stage-2` | data-based inquiry (pass `MeasurementContext`) |
| POST | `/inquiry/generate/problem-exploring-stage-2/from-job/{job_id}` | same, but auto-fetch measurement from agent-backend |
| POST | `/inquiry/submit-response` | evaluate answer → feedback + next step + misconception + concept coverage |
| POST | `/inquiry/generate/problem-generating` | author a solvable problem from the student's data |
| GET | `/inquiry/history/{user_id}` | session log (inquiries + responses) |
| POST | `/questions/generate` | tiered questions (difficulty auto from ability, or explicit) |
| POST | `/questions/easy` · `/intermediate` · `/advanced` | tiered questions at a fixed level |
| POST | `/students/profile` | upsert profile (sets ability band) |
| GET | `/students/profile/{user_id}` | read profile |
| GET | `/students/misconceptions/{user_id}` | misconception history |

## Status & next

**Done (Phase-1 — feature complete):** full staged flow (problem-finding → exploring
stage-1 → stage-2 → problem-generating) + submit-response; tiered question generation
(easy/intermediate/advanced, auto by ability); stateful session persistence (inquiries +
responses + `/history`); student model (profile, ability band, misconception history);
validated 6-id misconception taxonomy; deterministic concept-coverage (EN+ID); KG +
few-shot grounding; the seam wired both ways; core-logic test suite.

**Run tests:** `pip install pytest && pytest -q`

**Live (2026-06-04):** verified end-to-end against the Qwen server (generates real
inquiries + solvable problems with worked solutions); **wired into the Flutter tutor**;
prompts now emit inline **LaTeX** (`$…$`, JSON-safe) which the app renders natively.
Running on `192.168.1.13:8090` via the shared `sam3` conda env.

**Next (polish):** richer graded scoring (port `_score_inquiry_quality`); stage-2
**graph-image** input (needs a vision model — current Qwen is text-only, deferred);
EN/ID prompt polish.
