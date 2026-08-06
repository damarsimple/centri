# Evaluation-method adaptation — progress (2026-07-08)

> ⚠ **Corpus superseded 2026-08-06.** Entries below are dated and describe the **7-clip / n = 21**
> corpus. It is now **5 clips / 15 worksheets** — `fan-4027`/`fan-4028` (synthesized orbits) and
> `turntable-3` (tracker teleports) withdrawn, `fan-4656` added — and every aggregate was
> re-derived: BERTScore **0.799/0.824/0.828**, judge A **3.57/3.83/4.58**, judge B
> **3.72/3.72/4.18**, **κ = 0.31** quad over 180 pairs, gate **11/15**. Read any "21 worksheets" /
> "7 clips" below as history. **Axis 4 is the one aggregate NOT re-run.**
> Current state: `SESSION_CHECKPOINT.md`; method: `eval-framework.md` §4a.

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

---

## Update 3 — 2026-07-31 (a second LLM judge; the κ column stops being a dash)

Full record, with method, threats to validity and copy-paste reproduction:
**`judge-reliability-2026-07-31.md`**. Summary of what changed and what it means.

**Two raters, one rubric, one prompt.** `Claude Opus 5` (`claude-opus-5`, scored 2026-07-31, seven
blind sub-agents — one clip each) now scores the same 21 worksheets on the same 12 criteria as
`Qwen3.6-35B` (scored 2026-07-29, local endpoint, temperature 0). Both were sent the
**byte-identical prompt**: `run_llm_judge.build_prompt()` is now the single assembly point,
`tools/export_judge_prompts.py` freezes one file per worksheet, and
`tools/run_judge_from_prompts.py` replays it (`--model` for an endpoint, `--from-json` for agent
output). Without that, a score gap cannot be attributed to the judgement rather than to the
question.

**Result — the ordering reproduces, the score does not.**
- κ = **0.34** quadratic-weighted / 0.08 unweighted over 252 pairs; exact 33%, within-1 88%.
- Both raters put advanced top (Qwen 3.99/3.92/4.46; Claude 3.45/3.43/3.96). Claude is harsher by
  a near-constant −0.5 at every level.
- Best-agreed: `cognitive_demand` (κ 0.59, r 0.78) — the criterion the tier claim rests on.
- **No agreement at all: `grounding_accuracy` (κ −0.04, r −0.05, within-1 on only 52%)**, though
  its *means* match (3.10 vs 3.14) — a mean-only comparison would have hidden this entirely.
- **Consequence for every future report:** quote rankings from the judge, never an absolute level.
  "4.12/5 → 8.2/10 vs P-MAGIC's 8.2–8.6" is a property of the rater; rater B gives 7.2.

**The case for the teacher panel, in one row.** On `turntable-3` advanced — the worksheet whose
number is a known tracker artifact (7.45 vs a true 5.85) — Qwen scored grounding **5** and Claude
**2**. A single rater reports whichever it draws.

**Control: the judge is deterministic, the writer is not.** Re-running Qwen on the frozen prompts
two days later reproduced the original **exactly** — 252/252 ratings, zero differences, κ = 1.00
(`material_work/_eval/judge_qwen_2026-07-31/`). So the judge gap is a rater difference, not run
noise, and the 07-29 run demonstrably had the same prompt. Contrast generation, which does not
reproduce (checker 19/21 → 16/21). Quote single-run *judge* numbers with the run named; never
single-run *generation* numbers.

**κ implementation traps, both hit and both now pinned** (`tools/tests/test_judge_agreement.py`,
7 tests): the expected term takes a single `1/n²` — an extra `÷n` makes κ scale with sample size;
and zero-variance criteria are **`n/d`, not 0.0**, or "always agreed" prints as "never agreed".
Weighting is quadratic, because 4-vs-5 on an ordinal scale is a near miss.

**Open, and it blocks the human panel:** `grounding_accuracy` appears to ask two questions at once
— "do the numbers trace to the measurement?" and "do the relations printed beside them close?" —
which the deterministic checker separates and the rubric does not. Split it (or tighten its
wording) **before** teachers score it, or the human κ inherits the same ambiguity.

### Files touched
New: `tools/export_judge_prompts.py`, `tools/run_judge_from_prompts.py`, `tools/judge_agreement.py`,
`tools/tests/test_judge_agreement.py`, `docs/judge-reliability-2026-07-31.md`.
Modified: `tools/run_llm_judge.py` (extracted `build_prompt`), `tools/build_pmagic_tables.py`
(`--judge-dir-b`, `kappa_map`, two-rater table), `docs/eval-framework.md` (§4a).
Outputs: `material_work/_eval/judge_claude_2026-07-31/`, `judge_qwen_2026-07-31/`,
`judge_agreement_2026-07-31.{md,json}`, `pmagic_tables.{md,tex}`.

---

## Update 4 — 2026-07-31 (Axis 4 scored for the first time on the current figures)

Full record: **`axis4-multimodal-2026-07-31.md`**.

**The gap.** Axes 1–3 are text; Axis 4 asks whether the FIGURES are right and needs a rater that
can see them. The only Axis-4 output that existed was dated 06-25 — before the pedagogy rework and
before the 07-27/07-31 figure fixes — so it described figures that no longer exist. `Claude Opus 5`
(7 blind agents, one clip each) scored all 21 worksheets on the 11 multimodal criteria.

**Modalities are per TIER and absence is not failure.** The basic tier ships no table by design, so
its four table criteria are `n/a` and excluded from every mean. Scoring an absent modality would
penalise a tier for a figure it was built not to show.

**Results by modality (basic / intermediate / advanced):** image–text 3.71 / 3.50 / 3.86;
text–graph 3.36 / 3.14 / 3.25; text–table n/a / 3.36 / 3.25; **annotation correctness 4.29 / 4.43 /
4.29**; all scored 3.59 / 3.40 / 3.45.
- **No tier ladder in Axis 4** (flat, non-monotonic) — the same renderer draws all three tiers, so
  **the difficulty claim rests on the prose alone** and Axis 4 must not be cited for it.
- **`annotation_correctness` is the strongest row in the whole evaluation** — independent
  confirmation that the 07-31 direction fix landed, from a rater never told a fix had happened.
- **Weakest row is `graph_sense_physical` (2.29–2.71)**, i.e. figure-versus-physics contradiction.

**The defect it caught, a same-day regression.** The `REST_WORDS` change of 07-31 printed
"not turning" on rest bands. The segmenter marks spans INACTIVE that contain real motion, so the
label turned a silent error into a printed falsehood: `computerfan-4029` had a band captioned
"not turning" containing samples at **24.14 rad/s**. **11 of the 12 rest bands in the corpus
carried a label their own curve contradicted.** Fixed by `_rest_label_is_contradicted` — the word
is suppressed when the band's samples exceed 5% of the series max, the shading stays (a colour is
not a claim); 7 tests in `tools/tests/test_phase_label_honesty.py`; all 7 clips re-rendered,
`verify_figures` clean. **The segmentation itself is still wrong and is open.**

**Retracted:** "the redraw introduced zero new gate failures — that is the evidence the figure work
did not disturb the text". The gate was clean and the figure was false; the gate checks that
annotations trace to the seed and never asks whether a band label agrees with the curve beneath it.
**A clean gate is evidence about the gate's questions, not about the figure.**

**Other open figure defects** (not regressions, found by the same run): "clip average" is really the
turning-window mean on every time-series plot; the basic turns-vs-time graphs contradict their own
printed captions on two clips; tabulated `a_c` never closes under `a_c = ω²r` and the intermediate
tier asserts the false substitution; fitted-circle offsets of 9–21% of r on three clips; assorted
render bugs (clipped table titles, overlapping callout boxes, inverted trajectory y-axis, ASCII
`m/s^2`).

**PIPELINE HAZARD, worth more than the finding.** Every workspace carries its own **frozen copy of
`analysis/`**, and re-rendering from inside a workspace imports THAT copy, not `workspace_lib/`.
A renderer edit plus a re-render appeared to succeed and changed nothing. Sync first:
`for d in workspaces/job_*/; do cp workspace_lib/analysis/render/figures.py "$d/analysis/render/figures.py"; done`
— and confirm by diffing the copies, not by re-running and hoping.

### Files touched
New: `tools/export_multimodal_prompts.py`, `tools/build_multimodal_table.py`,
`tools/tests/test_phase_label_honesty.py`, `docs/axis4-multimodal-2026-07-31.md`.
Modified: `tools/run_llm_judge.py` (Axis-4 rubric + `build_multimodal_prompt`),
`workspace_lib/analysis/render/figures.py` (+ the 7 frozen workspace copies).
Outputs: `material_work/_eval/multimodal_axis4_2026-07-31.md`, `presentation/axis4_table.tex`.
