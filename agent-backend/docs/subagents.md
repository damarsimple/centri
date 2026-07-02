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
  **`llama.cpp-lab1/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf`** (4-bit), served OpenAI-style
  at `192.168.1.205:8083`. Model routing is in `.pi/agent/models.json` (bind-mounted at
  runtime; `config/pi-models.json` is the baked-image fallback).
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
(C) and the learning material (D). All four subagents run in parallel:

| Subagent | Output | Blocks LaTeX? |
|---|---|---|
| A — Video Annotation | `video_annotation/annotated_video.mp4` | No (separate deliverable) |
| B — Figure Generation | 9 PNGs in `plots/` | **Yes** |
| C — Question Generation | `data/questions.json` | **Yes** |
| D — Learning Material | `data/material.json` | **Yes** |

LaTeX compilation (the gated render step, or inline) starts only after
`plots/summary_panel.png`, `data/questions.json` **and** `data/material.json` exist.

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

## C — `question-gen-subagent.md` — the *only* pedagogy here

> **2026-06-21 — reworked to the P-MAGIC difficulty-tier method** (Hwang et al.,
> `document-3.pdf`). Replaced the old Bloom's-6-level scheme with **three difficulty
> levels** and per-question **modality tags**, so the output matches Vinsa's paper and
> feeds her multimodal evaluation. Active def: `.pi/agents/circular-motion.subagent-c-questions.md`
> (legacy copies `.pi/agents/question-gen-subagent.md`, `.pi/agent/agents/question-gen-subagent.md`
> kept in sync). See [PAPER_GAP_ASSESSMENT.md](../../PAPER_GAP_ASSESSMENT.md) and the
> session checkpoint.

Generates a **difficulty-tiered, multimodal question bank** grounded in `stats.json` →
`data/questions.json` (+ `question_quality_log.json`, `difficulty_distribution.json`).
This is the full extent of "teaching" in `agent-backend`.

- **9–12 questions** across three tiers (Bloom-mapped, but the output axis is difficulty):
  - **easy** = remember/understand (recall/read one quantity; *no formula in the stem*; round to 2 dp),
  - **intermediate** = apply (one relationship computed, e.g. `v=ωr`, `a_c=ω²r`; working in `solution`),
  - **advanced** = analyse/compare (multi-step / two-scenario reasoning).
- Each question is tagged with a content **`format`** (`text|image|graph|table`) and the
  set spans all four, so the multimodal ablation (text-image/-graph/-table) has material.
- **Schema** = a JSON **object** `{object_name, scenario, questions:[…]}`. Each question
  carries both `stem` (the app reads this) **and** `question` (the LaTeX report reads this)
  with identical text, plus `difficulty`, `format`, `answer`, `unit`, `solution`, `hints`,
  `given`. (The old bare-array + `bloom_level` shape was silently rejected by
  `app/result_data.load_worksheet`, which needs a dict — the rework fixed that.)

**Contrast with `fastapi-gpt`:** this is *one-shot, identical every run, no learner
model*. Her inquiry tutor is *interactive, staged, ability-adaptive, misconception-
tracking*. The worksheet is a fine artifact but is **not** a substitute for the tutor —
see [architecture-overview.md](architecture-overview.md).

## D — `material-gen-subagent.md` — the grounded learning material

> **2026-06-21 (refresh 5)** — added so the pipeline emits **learning material**, the
> artifact Vinsa actually evaluates (not questions). Def: `.pi/agents/material-gen-subagent.md`.

Writes an **authentic, phenomenon-grounded learning passage** → `data/material.json`. Unlike
Subagent C, its numbers are pre-computed deterministically: **Step 6** (`analysis/run.py`)
calls `analysis/material_seed.py` to write `data/material_seed.json` — the variables, the
formula relations, the angular-acceleration block, and a **time-anchored ω(t)** sampled from
`kinematics.csv`. Subagent D turns that seed into fluent prose and **never invents a number**.

- **Five sections** (fixed headers): Scenario · The variables we measured · How the variables
  are related · What the video shows over time · Reading the figures.
- **Schema** = `{object_name, scene_title, sections:{<header>: <prose>}}`.
- Rendered into the PDF by `render/report.py` (`_material_block`) as the leading
  **Learning Material** section.
- Evaluated by `tools/run_material_eval.py`: raw BERTScore F1 vs an authentic textbook
  reference (OpenStax §6.2) → **0.840 ± 0.002** (5 objects).
- **Quick path** (validation / recovery, same prompt+model): `tools/{build_material_seed,
  generate_material}.py`. Qwen needs thinking-budget headroom (`max_tokens≈24000`) or
  `content` returns empty.

## Report compile — LaTeX (seeded `render/report.py` + `compile_latex.sh`)

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
