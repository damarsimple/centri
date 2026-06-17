# Subagents & Agent Harness

> The `pi` subagents the orchestrator spawns, the model/harness config, and the
> "agent behavior" details that matter when changing prompts. Source:
> `.pi/agent/agents/*.md`, `.pi/agent/models.json`, `config/pi-models.json`. Companion:
> [pipeline-internals.md](pipeline-internals.md), [agents-behaviour.md](agents-behaviour.md).

> **⚠️ 2026-06-12 — rendering is now SEEDED; subagents A/B VERIFY (supersedes the
> hardening note below for video + figures + report).** Hand-authored layout kept
> reintroducing bugs (missing PDF images, wrong coordinate space, stray numeric values),
> so the rendering moved into seeded deterministic modules the orchestrator runs **inline
> as a required STEP 0**: `analysis/render/figures.py`, `render/report.py` (LaTeX),
> `render/annotate.py` (video). The figure + video subagents now **run that module and
> verify** rather than author. **Question generation (C) is unchanged — still a true LLM
> author.** Full story: [improvement-changelog §12](improvement-changelog.md). The note
> below remains the history for why C carries its HARD RULES.
>
> **2026-06 hardening (subagents kept as LLM agents — not frozen).** All three
> subagent definitions were tightened to remove the failure modes flagged in
> [pipeline-internals §7](pipeline-internals.md):
> - **No hardcoded example numbers.** Each def now carries a HARD RULE: read values
>   only from this job's `stats.json` / `kinematics.csv`; every literal number in the
>   prompt is an illustrative placeholder, never to be copied.
> - **Stale file refs fixed:** `phases.json` → `stats["phases"]`; cropped video is
>   `roi/cropped.mp4` (no `cropped_iter<N>` / `roi_crop_meta["iteration"]`).
> - **Annotation = symbol-only, no values.** The annotated video labels variables by
>   symbol (`r`,`v`,`ac`,`w`) with a definitions legend and **never overlays measured
>   numbers** — students measure, not read answers. A vetted reference implementation
>   embodying this is seeded at `workspace_lib/analysis/render/annotate.py`; the
>   annotation subagent is pointed at it to run/adapt rather than re-author.

## Harness & model

- The pipeline runs on the **`pi` agent CLI** (`worker/tasks.py` calls
  `pi -p <prompt> --mode json|text --model <model>`).
- All agents — orchestrator + 4 subagents — use one model:
  **`llama.cpp-lab2/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf`** (4-bit), served OpenAI-style
  at `192.168.1.205:8083`. Model routing is in `config/pi-models.json` (baked into the
  image as `/root/.pi/agent/models.json`).
- Subagents are spawned via the orchestrator's `subagent` tool and run **inline in
  the orchestrator's LLM context** — their intermediate reasoning is embedded in the
  main session JSONL, not stored separately (a known debugging limitation).
- **Context-passing convention (a hard rule):** pass *file paths only* for large data
  (video, CSV, cache JSON); inject `stats` dict **values** directly as context, never
  as a path.

## Spawn timing & gating

Once `data/stats.json` exists, the orchestrator first runs the seeded renderers **inline
(STEP 0)** — `analysis.render.figures` → `verify_figures` → `analysis.render.annotate` —
then spawns the subagents to verify/polish that output (A, B) and to author the questions
(C). All three subagents run in parallel:

| Subagent | Output | Blocks LaTeX? |
|---|---|---|
| A — Video Annotation | `video_annotation/annotated_video.mp4` | No (separate deliverable) |
| B — Figure Generation | 9 PNGs in `plots/` | **Yes** |
| C — Question Generation | `data/questions.json` | **Yes** |

LaTeX compilation (subagent D, or inline) starts only after `plots/summary_panel.png`
**and** `data/questions.json` both exist.

## A — `video-annotation-subagent.md`

**Now (2026-06-12): runs `python -m analysis.render.annotate` and verifies it.** The
seeded renderer draws the overlays onto the **cropped** video, scales every overlay to
the frame resolution (`_S = max(w,h)/720`, so labels aren't hairlines), and puts the
title + legend in a **banner above the video** so the info box never covers the tightly
cropped footage. The subagent's def (rewritten in `.pi/agents/` — the short path pi
loads) tells it to run that module, verify a contact sheet, and only adapt
`render/annotate.py` if a pass genuinely looks wrong — never to hand-roll an overlay or
draw numeric values. The detailed visual spec below is what `render/annotate.py`
implements (it descends from the old 482-line hand-authoring def):

- Reconstructs object position from `kinematics.csv` polar data — **never** draws from
  raw `api_cache.json`.
- **Vision-in-the-loop self-refinement**: up to 3 render passes, each extracting a
  contact sheet and scoring a ~20-item checklist (alignment, colors, labels, legend,
  peak-ac border); patches and re-renders on failure; emits `annotated_video_DRAFT.mp4`
  if still failing after 3 passes.
- Fixed visual grammar: bright-green orbit circle (thickest), cyan `w` arrow (tangent),
  red `ac` arrow (inward), yellow `r` line. ASCII-only labels.
- **Pedagogically deliberate rule:** *no numeric values are rendered* — only the
  symbols `w`, `ac`, `r`, so students compute the values themselves. (Worth preserving
  if you redesign output.)

## B — `figures-gen-subagent.md`

**Now (2026-06-12): runs `python -m analysis.render.figures` + `verify_figures` and
verifies it.** The seeded module produces all 9 figures into `plots/` from `stats.json`
+ `kinematics.csv` (phases via `stats["phases"]`, **not** a `phases.json`):
`annotated_image`, `annotated_graph`, `annotated_table`, `trajectory`, `radius_t`,
`theta_t`, `omega_t`, `ac_t`/`v_t`, and the 2×4 `summary_panel` — phase-colored bands,
SI-unit axis labels, scene title, 150 dpi. It plots trajectory geometry from the cropped
`kinematics.csv` `x_px,y_px` and writes `figure_qa.json`, so the deterministic
`verify_figures` gate passes by construction. The subagent runs it and inspects the
panels, adapting `render/figures.py` only if one looks wrong.

## C — `question-gen-subagent.md` (280 lines) — the *only* pedagogy here

Generates a **static 8-question worksheet** grounded in `stats.json` → `data/questions.json`
(+ `question_quality_log.json`, `bloom_distribution.json`). This is the full extent of
"teaching" in `agent-backend`.

- Fixed specification: exactly 8 questions, fixed Bloom levels (Remember→Evaluate),
  fixed formats (numeric/MCQ/short-answer), fixed difficulty mix.
- Each question is self-contained (all values in the stem), MCQ distractors map to named
  misconceptions, short-answers include a teacher model answer + marking notes, numerics
  carry `answer_exact` + ±2% tolerance.
- Runs a `self-verification` block (asserts aᶜ=ω²r etc.) before writing.

**Contrast with `fastapi-gpt`:** this is *one-shot, identical every run, no learner
model*. Her inquiry tutor is *interactive, staged, ability-adaptive, misconception-
tracking*. The worksheet is a fine artifact but is **not** a substitute for the tutor —
see [architecture-overview.md](architecture-overview.md).

## D — LaTeX report (seeded `render/report.py` + `compile_latex.sh`)

**Now (2026-06-12): the `.tex` is seeded, not hand-authored.** The orchestrator runs
`python -m analysis.render.report` to generate `student_edition.tex` + `teacher_key.tex`
from `stats.json` + `questions.json`, then `latex-skill/scripts/compile_latex.sh` builds
the PDFs (auto engine detection, multi-pass, error parsing, PNG previews). `report.py`
sets `\graphicspath{{../plots/}…}` so figures resolve regardless of the compile CWD —
fixing the bug where a hand-written `\includegraphics{plots/...}` resolved to a
nonexistent path and pdflatex silently shipped **imageless** PDFs — and null-guards/escapes
every value (no more `\SI{N/A}{rad/s}`). The agent verifies the rendered PDF actually
contains the figures (e.g. `pdfimages -list`).

## Agent-behavior caveats (re-stated — important before editing)

- **Hardcoded example numbers.** `figures-gen` and `question-gen` embed values from one
  reference run (r=0.1514, ω=6.042, cx=549.2…). The model must substitute real
  `stats`/CSV values; if it copies the examples, output is silently wrong. Consider
  replacing with placeholders when you touch these prompts.
- **Duplicate subagent copies.** `.pi/agents/` (4 files) and `.pi/agent/agents/`
  (3 files) both exist; `worker/tasks.py` symlinks `~/.pi` into each workspace. Confirm
  which copy is authoritative before editing.
- **Filename drift** between orchestrator (`cropped.mp4`, `iterations`) and subagents
  (`cropped_iter<N>.mp4`, `iteration`) — see [pipeline-internals.md §7](pipeline-internals.md).
