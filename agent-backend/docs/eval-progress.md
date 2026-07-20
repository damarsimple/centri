# Evaluation-method adaptation — progress (2026-07-08)

Session goal: adapt Utami's (2025) dissertation evaluation method + tooling to Centri, and produce
this week's method-with-preliminary-results deck. Plan: `~/.claude/plans/prancy-scribbling-thimble.md`.
Scope agreed with user: **set up code + docs for the full #1–#4 pipeline, preliminary numbers only**
(no production run), **teachers deploy next week**.

Source rubric extracted from `Dissertation_Ika Qutsiati Utami_03102025.pdf` (Tables 8/9 verbatim,
Study-2 rubric §3.2.4, BLEU scale §3.2.4, ICC/κ procedure §3.4.3). Table 10 (socialization) NOT
adopted (decision #5).

## Update 2 — 2026-07-08 (post-meeting: P-MAGIC rubric + video lit + formalized framework)

Meeting reframed the eval for our real unit (learning **material**, not problems) and surfaced the
**P-MAGIC paper** (`document-4.pdf`, Sari/Hwang et al., JECR 2026) whose **Table 2** is a
modality-organised rubric — the source for a new multimodal axis. Actions:
- **Reconciled rubric** (`eval-rubric-ika.md`): Axis 1 linguistic kept; **Axis 2 slimmed** to
  comprehension / structure / concept / realistic / variable-name (dropped problem-only
  answerability / solvability / multiple-strategies → retires the "expository-unfair" caveat);
  **Axis 3** adds **video_recognition_quality**; **NEW Axis 4 multimodal** = P-MAGIC
  image-text / text-graph / text-table blocks + annotation_correctness (on video).
- **New `eval-framework.md`** — the formal method: 4 axes + reconciliation table; layers (gate →
  automatic BERT/BLEU/STS/LSTM → semi-automatic MLLM-as-judge [VideoJudge recipe] → human
  per-modality → κ/ICC/Pearson); the video-recognition sub-axis; contribution ledger.
- **`related-work-positioning.md`** — added the video literature review + sharpened niche + **hard
  P-MAGIC differentiation** (video vs sensor, material vs problems, grounding gate; annotation-on-video).
- Web-search literature review saved (Tracker / CV-tracking / VLM-QG / DiffPhy / VideoJudge /
  MLLM-judge); PhyEduVideo noted (text→video, the inverse direction).

**Next:** update/rebuild the weekly deck to the formalized method; then fix video-frame annotation
(adopt P-MAGIC Hough/OpenCV + phase-labeling) and rethink material-supply order (material waits for
annotated video first); then implement the reconciled rubric in `run_llm_judge.py` +
`build_rater_sheet.py`.

## Update 3 — 2026-07-08 (implementation: deck + rubric-in-code + annotation started, then STOPPED)

Built on Update 2. Status of the follow-through work:
- **Weekly deck (new)** ✅ `presentation/centri-eval-framework-2026-07-08.tex` — reframed around the
  formalized method (video niche, P-MAGIC contrast, 4-axes/5-layers diagram, reconciliation table,
  MLLM-judge + video-recognition contributions, salvaged preliminary results). Compiles clean, 12 pp,
  0 overfull; the diagram fixes the "axis vs layer" overload.
- **Reconciled rubric in code** ✅ `tools/run_llm_judge.py` + `tools/build_rater_sheet.py` — text
  judge now scores 12 criteria / 3 axes (linguistic, structural/comprehension, physics-tier); Axis 4
  multimodal (11 rows) exported for the rater sheet + future vision judge; `video_recognition_quality`
  left instrumented. Verified: cross-import + prompt/definition coverage checks all pass.
- **Phase 3 annotation + reorder** — PARTIAL, then stopped at user request:
  - ✅ **validated** `render/figures.py`: ω tangential arrow + "ω = X rad/s" on the annotated frame;
    per-figure manifest in `figure_qa.json["annotations"]` (rendered + eye-checked on a copy of
    job_7fa4ed69; `verify_figures` reads only `["trajectory"]`, so safe).
  - ⚠️ **written, NOT yet compiled/run** `analysis/material_tiers.py` (`_annotation_note` appends real
    annotations to each tier's figures text) and `render/annotate.py` (PIL/freetype swap → ω on the
    VIDEO; Pillow availability unconfirmed, needs a render + frame eye-check).
  - ⛔ **not started**: phase text-labels in `_shade_phases` + degrees-per-second on the basic angle
    figure; orchestrator sequencing (figures → material); optional `annotation_correctness` gate.
- Full resume state (files, line areas, validation harness, gotchas) is in memory:
  `centri-annotation-reorder-progress`. Everything still **uncommitted**.

## Done this session

### A1 — LLM-judge aligned to Utami Tables 8–9  ✅
- `tools/run_llm_judge.py` rewritten. Rubric is now 3 axes / 11 scored criteria + achieved_bloom:
  - *authenticity_linguistic* (Table 8): motivating_context, language_clarity, solution_steps,
    solution_strategy_variety, cognitive_demand
  - *mathematical* (Table 9): answerability, structure_clarity, multiple_strategies
  - *physics_tier* (ours): difficulty_fit, concept_accuracy, grounding_accuracy
- New `--difficulty-report` arg feeds the gate's measured EI per tier into the judge as ground truth.
- Report now emits per-axis + per-criterion means and a JSON sidecar. Old `TODO(IKA)` removed.
- **Bug fixed:** `SYSTEM.format()` choked on literal JSON braces in the prompt → switched to
  `.replace("{level}", ...)`. (This was also latent in the pre-existing version.)

### A2 — correlation/reliability stats  ✅ (new)
- `tools/eval_stats.py` (numpy-only): Cohen's κ + % agreement (inter-rater), ICC(2,k)
  (human↔LLM, two-way random / average measures / absolute agreement), Pearson (auto↔human).
- Tidy-CSV in (`item,dimension,rater,role,score`), md+json out.
- **Verified** against a hand-computed synthetic set (Pearson 0.94 matched).

### A3 — human-rater path + rubric doc  ✅ (new)
- `tools/build_rater_sheet.py`: one CSV per teacher (item × rubric row), **imports the rubric from
  run_llm_judge** so human + LLM score identical criteria (precondition for ICC). Output ingests
  straight into `eval_stats.py`. Also writes a `passages.md` for raters.
- `docs/eval-rubric-ika.md`: single source of truth (Tables 8–9 verbatim + tier block + BLEU scale
  + stats). Shared by A1 and A3.
- **Verified** end-to-end on the fan export (sheet builds, round-trips through eval_stats).

### B — generate-K-gate-select  ✅ (behind flag)
- `tools/generate_tier_material.py`: `--candidates K` generates K drafts/tier, runs each through
  `material_gate.tier_gate`, selects fewest-issues (deterministic tie-break = earliest draft),
  writes a `material.<tier>.candidates.json` log. **K=1 (default) = unchanged behaviour.**
- Utami's generate→review→select pattern; the durable answer to the 35B self-correction limit.
- **Verified live** (K=2, fan basic): 2 drafts generated + gated + selected. Both drafts still had
  the "tracked" vocab tic (3 issues) — exactly the limitation this addresses; higher K should reach
  a clean draft.

### C + D — positioning + effectiveness docs  ✅
- `docs/related-work-positioning.md`: Centri's niche vs Utami's SLR (video-CV + tiered physics;
  sensing/domain/difficulty/determinism contrasts; structural-vs-depth caveat).
- `docs/effectiveness-study-blueprint.md`: her Study-3 design adapted (EG/CG, 6wk, ANCOVA/Pearson/
  stepwise, TAM) + the **app-instrumentation list** we must add before running it.

### E — preliminary run  ✅ (real numbers, labelled preliminary)
Outputs in `material_work/_eval/preliminary/` — 5 objects × 3 tiers = 15 passages from existing
`vinsa_export` outputs. Summary: `PRELIMINARY_SUMMARY.md`.
- **LLM-judge tier ladder is visible:** cognitive_demand 2.2→2.6→4.0; solution_steps 1.2→2.0→3.0;
  achieved Bloom Understand→Understand→**Analyze** (4/5 cases).
- **Honest findings:** grounding_accuracy drops at advanced (4.4→3.6→1.0 — per-instant claims on
  oblique clips, same as the gate flags); the mathematical axis is expository-unfair (problem-rubric
  vs passage); EI monotonicity fails 4/5 (advanced trades breadth for depth), FK grade rises 5/5.
- **Auto baseline:** BERTScore F1 = 0.830 ± 0.014 (n=75), whole-passage F1 0.823, diversity 0.311.

### F — weekly deck  ✅
- `presentation/centri-weekly-2026-07-08.tex` (+ compiled `.pdf`, 12 pp). Reuses the 06-30 preamble.
  Frames: why a new method → the 4-axis method (diagram) → the rubric → tooling shipped → preliminary
  results → honest reading → status/next. **Compiles clean** (2 cosmetic tikz overfulls only).

## Verification status
- All four tools `py_compile` clean; cross-import sanity OK; `build_rater_sheet.CRITERIA == run_llm_judge.CRITERIA`.
- eval_stats hand-checked; rater sheet round-trips; judge ran on all 15; candidate-select smoke-tested live; deck compiles.
- **Not run:** existing `tools/tests/test_material_gate.py` (pytest missing in `.venv-eval`; my
  changes don't touch `material_gate.py`). Worth running once with system pytest:
  `PYTHONPATH=workspace_lib pytest tools/tests/test_material_gate.py`.

## Next (per plan, mostly next week)
- Deploy `build_rater_sheet.py` CSVs to teachers → real Cohen's κ / ICC / Pearson via `eval_stats.py`.
- Full production run with tier-matched references (`split_references_by_difficulty.py` +
  `run_multi_reference_eval.py`).
- Tune candidate-select K (does best-of-K reach 15/15 clean tiers?).
- Effectiveness study later (needs IRB + app instrumentation from the blueprint).
- **Nothing committed yet** — all changes are in the working tree.

## Files touched
New: `tools/eval_stats.py`, `tools/build_rater_sheet.py`, `docs/eval-rubric-ika.md`,
`docs/related-work-positioning.md`, `docs/effectiveness-study-blueprint.md`, `docs/eval-progress.md`,
`presentation/centri-weekly-2026-07-08.tex`.
Modified: `tools/run_llm_judge.py`, `tools/generate_tier_material.py`.
Preliminary outputs: `material_work/_eval/preliminary/`.
