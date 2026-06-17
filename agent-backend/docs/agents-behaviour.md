# Agents Behaviour Reference

> One place to understand **every agent** in `agent-backend`: what model it runs,
> what it reads, what it produces, and — crucially — **which parts are LLM-driven
> (non-deterministic) vs frozen (deterministic)**. Companion docs:
> [pipeline-internals.md](pipeline-internals.md) (step detail),
> [subagents.md](subagents.md) (subagent I/O), [data-contract.md](data-contract.md)
> (schemas), [`analysis/README.md`](../workspace_lib/analysis/README.md) (frozen pipeline).

## The harness

All agents run on the **`pi` agentic coding CLI** against a local **Qwen3.6-35B-A3B**
served via llama.cpp / vLLM (see `.pi/agent/models.json`). `pi` lets the model write
and execute Python inside the per-job workspace, call tools, and spawn subagents.
The worker (`worker/tasks.py`) shells out to it:

```
pi -p <prompts/orchestrator.txt> --mode json --model llama.cpp-lab2/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf
```

**Sampling note:** determinism is governed server-side (temperature/seed on the
inference server) — `models.json` sets no per-call sampling. Reasoning is on. Lower
temperature ⇒ less run-to-run drift in the agentic steps.

## The five agents

| # | Agent | Definition | Mode | Role |
|---|---|---|---|---|
| 1 | **Orchestrator** | `prompts/orchestrator.txt` | `pi --mode json` | Runs Steps 1–6, spawns subagents, compiles the LaTeX report |
| 2 | **Subagent A — Video Annotation** | `.pi/agent/agents/video-annotation-subagent.md` | `pi-subagent` | **Verifies** the seeded `render/annotate.py` overlay (orbit/ω/aᶜ/r, symbol-only, banner) |
| 3 | **Subagent B — Figure Generation** | `.pi/agent/agents/figures-gen-subagent.md` | `pi-subagent` | **Verifies** the seeded `render/figures.py` plots (9 + summary panel) |
| 4 | **Subagent C — Question Generation** | `.pi/agent/agents/question-gen-subagent.md` | `pi-subagent` | 8 exam questions → `questions.json` |
| 4b | **Subagent D — Figure Visual QA** | `.pi/agent/agents/figure-qa-subagent.md` | `pi-subagent` (multimodal) | **Retry-only**: looks at the plots, checks the circle sits on the points / labels OK |
| 5 | **Extractor** | `prompts/job-output-extractor.txt` | `pi --mode text` | Reports which output files exist (post-run) |

**Figure verification (after Subagent B).** A frozen deterministic gate
(`analysis/verify_figures.py`) runs on **every** job: `plots/figure_qa.json` (the bounds
of what was plotted) is checked against the cropped `kinematics.csv`, failing if they
don't match — catching the "trajectory plotted in full-frame space, circle floats off the
points" bug with certainty. Since the seeded `render/figures.py` writes both the plots
and `figure_qa.json` from the same cropped arrays, **this passes by construction**; the
gate is now a safety net against a verify-triggered re-render going wrong. Subagent D (the
multimodal visual QA above) runs **only if that gate fails**, feeding richer feedback into
a bounded re-render loop (≤2). The happy path is the instant deterministic check only —
no extra LLM pass.

Plus one **non-agent**: the frozen [`analysis/`](../workspace_lib/analysis/README.md)
pipeline, seeded into every workspace and *run* by the orchestrator (Step 6). It is
plain deterministic Python — **no LLM** — and owns all kinematics.

---

## 1. Orchestrator agent

**Reads:** `input_video.mp4`, `sidecar.json`, `pipeline_inputs` env, the seeded
`analysis/` package, the seeded `.pi/` config.

**Behaviour — the agentic / frozen seam:**

```
 Step 1  Scene parse + ffprobe            ┐
 Step 2  Remote SAM tracking (1 call)     │  AGENTIC — LLM writes Python.
 Step 3  Coordinate validation            │  Judgment: what to track, where the
 Step 4  Center bootstrap (user mark)     │  center is, how big the reference is.
 Step 5  Reference sizing → CONTRACT      ┘  Output: pipeline_inputs.json
 ───────────────────────────────────────────────────────────────────────
 Step 6  python -m analysis.run              FROZEN — deterministic, no LLM.
                                             Output: stats.json, kinematics.csv
```

**Hard rules it must obey** (from `orchestrator.txt` HARD RULES): tracking is
remote-only (never run SAM locally); exactly one tracking call (cached); never
fabricate numbers; **never reimplement or edit `analysis/`**. Step order strict 1→6.
Coordinates stay in cropped-video space everywhere **except** the `pipeline_inputs.json`
handoff: Step 5 emits the trajectory **and** center in raw full-frame (`"display"`)
space with `coordinate_space:"display"`, and the frozen `contract.py` does the single
display→cropped subtraction for both together. The agent must **not** crop-subtract the
contract trajectory by hand — doing so inconsistently (one run subtracted `y_off`, one
didn't, while the center stayed cropped) is what made IMG_3072 non-deterministic
(period 14.6% / `stable_mean_omega` 81% spread on the same video). See
[improvement-changelog.md](improvement-changelog.md) §10.

**Why the seam is here:** Steps 1–5 require perception judgment that genuinely
benefits from the model. Everything after the trajectory exists is arithmetic, and
when the model authored that arithmetic it produced 28 `stats.json` schemas / invalid
NaN / drift 8.9→1013 px on identical input. Freezing it removed that variance while
keeping the model where it adds value.

**Produces (sequential phase):** `pipeline_inputs.json` (Step 5), then via the frozen
pipeline `kinematics.csv` + `stats.json` + `active_mask.npy` (Step 6). After loading
`stats.json` it unpacks flat locals (`mean_omega`, `cx_px`, `period_s`, …) that the
LaTeX macros and subagent injection reference.

**Then (parallel wave, 2026-06-12):** first runs the three **seeded render modules
inline** — `python -m analysis.render.figures` → `verify_figures` →
`analysis.render.annotate` (STEP 0). It then spawns subagents A/B (to *verify* that
output) and C (questions), gates LaTeX on B+C, generates the `.tex` with
`python -m analysis.render.report`, compiles `student_edition.pdf` + `teacher_key.pdf`,
and writes `report.md`. The figures, the report `.tex`, and the annotated video are all
seeded deterministic code now — see §2–4.

---

## 2–4. The three subagents

Each runs as a `pi-subagent` on the same Qwen model with `systemPromptMode: replace`.
They consume the frozen `stats.json` / `kinematics.csv`; they do not compute physics.

**As of 2026-06-12 the rendering itself is seeded deterministic code** — A (video) and B
(figures) are produced by `analysis/render/{annotate,figures}.py` (run by the orchestrator
inline, STEP 0), and the subagents' role is **verify + optional light polish**, not
authoring (hand-authored layout kept reintroducing missing images / wrong coordinate
space / stray numeric values — see [improvement-changelog §12](improvement-changelog.md)).
The LaTeX report is likewise seeded (`render/report.py`). **C (questions) remains a true
LLM author** — it is pedagogy content, not layout. So A/B are now deterministic-by-default
(LLM only on a verify-triggered re-render); C stays non-deterministic.

| Subagent | Input (injected from `stats` + file paths) | Output | Blocks LaTeX? |
|---|---|---|---|
| **A Video Annotation** | cropped video, `kinematics.csv`, center/r/ω | `video_annotation/annotated_video.mp4` | No |
| **B Figure Generation** | flat stat values + `kinematics.csv` | 9 PNGs in `plots/` | **Yes** |
| **C Question Generation** | flat stat values | `data/questions.json` | **Yes** |

**Definitions hardened (2026-06, subagents kept as LLM agents — not frozen):**
- **No hardcoded example numbers.** Each def carries a HARD RULE: read values only from
  this job's `stats.json`/`kinematics.csv`; any literal number in the prompt is an
  illustrative placeholder, never to be copied. (Fixes the old "model copies cx=549.2"
  hazard.)
- **Annotation is symbol-only.** It labels `r`/`v`/`ac`/`w` + a definitions legend and
  **never overlays numeric values** — students measure, not read answers. A vetted
  reference embodying this is seeded at `workspace_lib/analysis/render/annotate.py`; the
  subagent runs/adapts it rather than re-authoring. (`render/annotate.py` is a
  *reference*, not a frozen replacement — the subagent stays an LLM agent.)
- **Stale paths fixed:** `phases.json` → `stats["phases"]`; cropped video `roi/cropped.mp4`.

**Contract dependency (watch this):** B and C prompts list their inputs as **flat**
stat names (`mean_omega`, `std_omega`, `cx_px`, `cy_px`, `active_duration_s`,
`tracking_coverage_pct`, …). The orchestrator's Step 6 unpacks exactly these from the
nested `stats.json` so injection keeps working. If you add a field a subagent needs,
expose it in that unpack too.

---

## 5. Extractor agent

A second, short `pi --mode text` run (`prompts/job-output-extractor.txt`). It does not
analyse — it inspects the workspace and reports which deliverables exist (student/teacher
PDFs, annotated video, summary panel, kinematics CSV). `worker/tasks.py::_parse_extractor_output`
turns its JSON into the `/result` file URLs.

---

## Determinism summary

| Layer | Agent? | Deterministic? | Guarantee |
|---|---|---|---|
| Perception (Steps 1–5) | Yes (Qwen) | No | Judgment; lower temp reduces drift |
| Kinematics (Step 6) | **No** (`analysis/`) | **Yes** | Same `pipeline_inputs.json` → byte-identical `stats.json` |
| Video A / Figures B / Report | **No** (`analysis/render/`) | **Yes** | Seeded modules; agent verifies. LLM only on a verify-triggered re-render |
| Questions (Subagent C) | Yes (Qwen) | No | Real LLM author — pedagogy content, not layout |
| Extractor | Yes (Qwen) | No | Reports file existence |

**Validate** the frozen layer with `python tools/gt_harness.py` (determinism +
phone-gyro accuracy). Validate the **agentic** layer by re-running `/analyze` on the
live stack — the harness cannot exercise Qwen-authored perception.
