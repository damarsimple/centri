# Learning-material rework — implementation status

Snapshot of the "Learning-Material Quality Rework + Notes/Feedback Backlog" plan. Built on
commit `b59cf79` (clean tree). Everything below is **code + offline tests**; anything LLM-live
(regeneration, eval re-runs, a live job) is a lab-runbook step (see bottom) and is **not yet
validated live**.

## Done (implemented + offline-verified)

### WS-2 — Gate unification  ✅
- **New `agent-backend/workspace_lib/analysis/material_gate.py`** — the single source of truth:
  arithmetic closure, number grounding (`allowed_values`/`ungrounded_numbers`, extended with the
  angle-milestone values), tier compliance, motion faithfulness, **new** `vocab_issues`
  (tracking + dynamics), `story_fence_issues`, `cross_tier_issues` (title equality, per-tier
  worked-instant compliance/uniqueness, EI monotonicity), and the live `tier_gate`.
- **v=ωr drift resolved:** intermediate now requires the structured `a_c = ω²·r` and the `v=ωr`
  requirement is gone (matches the current tier policy).
- `tools/grade_material_grounding.py` → thin wrapper over the module (+ vocab + cross-tier
  sections). `tools/grade_material_difficulty.py` → imports the shared EI counters.
- **Tests:** `agent-backend/tools/tests/test_material_gate.py` — 8/8 pass.

### WS-1a — Naming + seed hygiene  ✅
- `common.py dedup_display_name()`; wired into `render/report.py`, `render/figures.py`, and
  `material_seed.py` (both `object_name` and `scene_title` deduped; degenerate `"<X> on <X>"`
  falls back to object name). `_facts()` uses `object_name`, never the composite.
- Seed stores **unsigned** ω and v (`abs`) — kills the −2.12 vs 2.08 prose/table contradiction.

### WS-3.1 — Seed milestones + narrative context  ✅
- `material_seed.angle_milestones()` (first 90/180/270/360° crossings, rebased; oblique guard
  keeps only 180/360). New seed fields `angle_milestones` + `narrative_context` (reads
  `sidecar.json scene_context`, VLM notes fallback). Milestones fed to `_facts()` for basic only.

### WS-1b–1e + WS-2 main — `material_tiers.py` rework  ✅
- **`_generate_frame()`** — one shared 5W+1H narrative frame per job (deterministic fallback);
  its `scene_title` hard-overwrites every tier, so tiers can no longer each invent a generic
  "Decelerating Circular Motion on a Turntable".
- **`TIER_ANCHORS`** — distinct worked instants per tier (fixes advanced ≈ intermediate);
  skipped when unreliable/empty.
- HARD RULE 8 rendered from the shared `TRACKING_VOCAB_HUMAN`; **new RULE 8b** (kinematics-only,
  `DYNAMICS_VOCAB_HUMAN`); RULE 1 story-vs-grounding carve-out.
- Tier-content updates (basic teaches the angle milestones + names the new figure; advanced EI
  floor). `main()` restructured: frame → 3 tiers (per-tier `tier_gate` + 1 regen) → cross-tier
  check → one targeted regen if budget remains. Gate JSON gains `frame` + `cross_tier` blocks.
- `difficulty_level` added to each material JSON. `tools/generate_tier_material.py` now imports
  the authoritative `TIERS` (no more drift copy).
- **Test:** fake-LLM end-to-end (`scratchpad/test_e2e.py`) — titles equal, per-tier instants
  distinct, gate JSON has frame+cross_tier, `difficulty_level` set, no "X on X", live
  ungrounded-number check fires. All assertions pass.

### WS-3.2/3.3 — Basic angle-at-time figure  ✅
- `render/figures.py fig_angle_points_basic()` — CVD-validated categorical dots (palette passed
  the dataviz validator), direct labels, start marker, sweep arc; dots come from the SAME
  `angle_milestones()` the prose uses. Wired into `report.py` `FIG_META` + `TIER_ARTIFACTS`
  (basic "What the video shows over time"). Rendered + eyeballed on the synthetic fixture.

### WS-4 — tier → difficulty_level (user-facing)  ✅
- Additive `difficulty_level` key; report badge `"BASIC DIFFICULTY"`; orchestrator bullet 8b;
  eval header "Difficulty level". Machine keys/filenames stay `tier`.

### WS-5 — Surface material in the app + Defect B  ✅
- **Backend:** `result_data.load_materials`/`load_material_gate`; `MaterialLevel` schema +
  `JobResultResponse.materials`; `routes.get_result` wiring. **Defect B fixed:**
  `worker/tasks._resolve_report_pdfs()` globs `student_edition*.pdf` (basic preferred) so the
  hardcoded dead `student_edition.pdf` link is gone; `FilePaths.tier_pdfs` (additive/optional)
  carries per-difficulty URLs. Schema round-trip verified (materials present AND old cached
  results without materials/tier_pdfs still validate).
- **Flutter:** `sidecar.dart sceneContext`; `JobFiles.tierPdfs` + `studentPdfFor()`;
  `models/material.dart`; `JobResult.materials`; `results_screen _MaterialSection` (Basic/
  Intermediate/Advanced selector + section cards); `annotate_screen` scene-context field
  (pre-filled from VLM notes). `flutter analyze` clean.

### WS-6 — Eval tooling (code lands now; runs on the lab machine)  ✅ (code)
- `run_material_eval.py` — **pure-Python BLEU + ROUGE-1/2/L** columns (lab venv has no
  sacrebleu/rouge); complementary, not headline. Unit-checked.
- **New `tools/run_llm_judge.py`** — LLM-as-judge rubric (relevance, answerability,
  difficulty-fit, concept accuracy, annotation accuracy) + achieved-Bloom rating; IKA criteria
  marked TODO.
- **New `tools/split_references_by_difficulty.py`** — sorts the 19-ref set into
  basic/intermediate/advanced on the shared EI axis. Classifier verified.

### WS-7 — Docs  ✅ (partial)
- **New `docs/capture-protocol.md`** (face-on, red-tape marker, scale ref, start→spin-up→steady,
  10–15 s, target corpus incl. Zhongli toys, "3 scenarios × 3").
- **Spec** `docs/difficulty-tiered-material-spec.md`: §1a figure table updated (angle figure +
  current allowlists); §9 decision **resolved → option (b) tier-matched references**; new §10
  (no-4th-tier decision, Bloom/CLT literature mapping, future-work 2-video/force comparison).

## Verified this session (offline)
gate tests 9/9 · fake-LLM e2e all assertions · figure render+eyeball · report render (badge,
angle fig, no dup titles) · API schema round-trip (+ old-cached still validates) · PDF resolver
(tiered/single/missing) · BLEU/ROUGE unit checks · reference classifier · `flutter analyze`
clean · every changed Python parses/imports.

## LIVE-VALIDATED — 2026-07-05  (`192.168.1.205:8083`, Qwen3.6-35B, `.venv-eval`)
The generator was run live end-to-end against the inference server (reachable + serving). No
longer "lab-only unvalidated" — the core targets are met.

**5-seed sweep** (regenerated `8110ab0d`, `711fffe8`, `afe0f99f`, `cc9f02ce`, `a2627aa2` from
their seeds through the reworked `material_tiers`):
- **EI monotonicity 5/5** (basic→intermediate→advanced low→moderate→high) ✅
- **Titles equal 5/5** (shared frame overwrite; no drift) ✅
- **Cross-tier PASS 4/5** (711fffe8 leaves a per-tier-clean intermediate that still misses its
  assigned worked instant — a distinctness technicality, not a wrong number)
- **All tiers fully clean 3/5** (13/15 tiers); residual = single-word vocab flags.
- Gate JSON carries `frame` + `cross_tier` blocks on every run.

**Fixes landed this session (beyond the WS-1..7 rework):**
- **Gate false-positive fixed** — `_STEADY` no longer flags bare "does not speed up" on a
  decelerating clip (only "does not speed up **or slow down**"); regression test added.
- **ω² grounded** — the sanctioned intermediate of `a_c = ω²·r` (per-instant + mean) is now in
  `allowed_values`, so showing "squaring ω gives 86.16" is not read as ungrounded; test added.
- **Idiom guards** — vocab fence no longer flags "on track" / "work together / out".
- **Quote-given-quantities rule** — T and f are quoted from the seed, never re-derived (killed
  the wrong `T=0.994`/`f=1.01` class of errors).
- **Best-of-N failure-informed regen** — up to 2 re-rolls fed the exact gate faults, keep the
  draft with STRICTLY fewer issues (no lateral `recorded`→`pushes` trades); cross-tier gets a
  SEPARATE regen budget fed both the cross-tier fault and residual per-tier issues.
- **External hints file** — `workspace_lib/analysis/material_hints.md`, loaded and injected into
  the tier prompt as a NUANCES block. Steers the FIRST pass (`recorded`→`measured`, figure
  phrasing, "slows down" not "does not speed up or slow down", ω² is fine, use milestone times
  only). Live-confirmed: the hint eliminated the stubborn `recorded` (0 occurrences).

**Documented 35B limitation.** Qwen3.6-35B drafts well but self-corrects **poorly** on regen —
told "you used a banned word" it often re-emits it or trades it for another violation. So the
durable strategy is to steer the first pass via `material_hints.md`, not to lean on regeneration.
Full generalization (perfect gate on every stochastic run) needs a stronger model or a
review-and-select loop (cf. Utami's SocioMathLLM CoT candidate selection). Remaining flags are
proceed-but-flag (the pipeline never hard-blocks) and are stochastic single-word cases.

## E2E FULL-STACK SWEEP + 3 fixes — 2026-07-06

First real end-to-end run of the whole `video → perception → tracking → kinematics → material →
figures → PDF` chain through the **live orchestrator/queue** (prior validation was material-stage
only). Stack brought up locally: SAM3 tracker (`10.0.0.1:8086`), redis + celery worker + API
(`docker compose`, API on `10.0.0.1:8088`), Qwen `192.168.1.205:8083` via the `llama.cpp-lab1`
provider (worker `.env` PI_MODEL). Code is picked up per-job because compose mounts `./workspace_lib`
and `seed_pipeline` copies it into each workspace — no rebuild needed. **All changes below are
uncommitted working-tree edits.**

### Fix 1 — scene grounding reaches the story LLM  (`material_tiers.py::_frame_user`)
Symptom: bicycle story invented "a smooth wooden board" for a *marker on a bicycle tire*. Root
cause: the sidecar **was** honored (reference_geometry.label → `seed.scene_title` = "red object on
rear bicycle tire"), but `_frame_user()` fed only `object_name` ("red object") to the frame LLM and
dropped `scene_title`, so the model invented a generic surface. Fix: parse the mount from
`scene_title` ("<tracked> on <reference>") and pass it as an explicit "what it is mounted on — never
swap for a generic table/board/turntable" fact (skipped when it just repeats the object, e.g. "fan
blade on fan blade"); strengthened FRAME_SYSTEM rule 1. **Verified live:** regenerated bicycle now
says "clipped to the rear bicycle tire", 0 wooden-board hallucinations across the whole sweep.

### Fix 2 — radius consistent across tiers  (`material_tiers.py::_frame_user`)
Symptom: basic/intermediate said radius "0.08 m", advanced "0.075 m". Cause: the shared story quoted
`round(radius, 2)` (0.08) while tier bodies quote the precise seed `r` variable (0.075). Fix:
`round(radius, 3)`. Not a calibration bug — measured radii legitimately span 0.056–0.96 m by scene.

### Fix 3 — "biggest lever": gate vocab false-positives + push steering  (`material_gate.py` + `material_tiers.py`)
The dominant gate-fail cause was the tracking-vocab regex over-matching legitimate physics English:
`captur(e)` fired on "**captures** the inward acceleration", bare `track` on "circular **track**".
Fix (deterministic): `track`→verb-only (`\btrack(?:ed|ing)\b`), `capture`→video-context-only
(`(?:video|screen|image|frame)[ -]?captur\w*`); synced `TRACKING_VOCAB_HUMAN`. Unit-tested: false
positives clear, real pipeline words + `push` still caught. Separately, `push` is a *genuine*
kinematics-rule violation (names a force) the model kept using → FRAME_SYSTEM now steers to
"spin/twist/flick/nudge" and forbids push/shove.

### SAM3 crash fixed (separate infra bug) — see the SAM3 memory
`sam3cpp/api_master_sam3.py` hardcoded `num_chunks = 1`, so long videos ran one ggml context that
overflowed (`GGML_ASSERT: not enough space in the context's memory pool`, ~frame 1364) — NOT GPU
memory (only 6/32 GB used). Fix: `num_chunks = ceil(nb_frames/1000)`; each chunk is already a
separate worker subprocess with a fresh context and the merge logic already frame-sorts. Validated
live on the 5172-frame fan-doll video (6×862-frame chunks, 0 asserts). **This file lives in
`/home/damar/sams2`, a different repo — also uncommitted.**

### Sweep results (run 1, all 10 templates)
**3 clean passes** (bicycle, turntable-1, turntable-2) · **6 gate-fails, none from grounding or
radius** — 4 vocab (`capture`/`track`/`push` — the Fix-3 targets), 1 motion-desc (computerfan:
"steady spin" vs `motion_type=decelerating`), 1 arithmetic (roundabout-4048: a_c = ω²r computed
wrong) · **1 skipped** (fan-doll: SAM3 could track it after the chunk fix, but the orchestrator
retry-looped brute-forcing detection labels for the fast small "yellow toy" — a detection/tracking
limit, killed to unblock the queue). Grounding + radius fixes held on **9/9** material-generating
jobs.

### Sweep results (run 2 — Fix-3 validation, 9 templates, fan-doll excluded) — PARTIAL, PAUSED at 5/9
Confirms Fix-3 works. First 5 jobs: bicycle PASS, computerfan-4029 PASS, fan-4027 PASS, fan-4028
PASS, roundabout-4046 FAIL.
- **Vocab lever CONFIRMED:** fan-4027 (prior track/push/capture fail) and fan-4028 (prior "captures"
  fail) both now `all_passed=True`; roundabout-4046's prior "capture" vocab fail is also gone. No new
  vocab false-positives. Stories now say "flick"/"twist" instead of "push" (steering works). Grounding
  + radius still clean on all 5.
- **New leading residual = motion-description faithfulness (stochastic).** roundabout-4046 failed
  instead on advanced "constant rate" vs `motion_type=decelerating` — the SAME class as computerfan's
  prior fail (which passed this run stochastically). So the decelerating scenes (computerfan,
  roundabout family) are a coin-flip on motion wording. **This is the next lever**, alongside the
  roundabout-4048 arithmetic (a_c) class.

**RESUME LATER — rerun still live, PAUSED at 5/9** (2026-07-06). Stack left UP (SAM3 10.0.0.1:8086,
redis/worker/api compose, Qwen 205). roundabout-4048 was running; turntable-1/2/3 queued (expect
pass — turntables passed clean in run 1). Rerun job_ids saved in `agent-backend/.rerun_jobmap.tsv`
(also scratchpad). To finish: poll `GET /status/{id}` for the last 4, spot-check gate JSON in each
`workspaces/job_<id>/analysis_output/data/material_tiers_gate.json`. Final run-2 tally = (5 seen: 4
pass / 1 motion-desc fail) + turntable-1/2/3.

## Remaining / not done
- ~~WS-7.2 backlog table~~ ✅ · ~~orchestrator Subagent-D prose~~ ✅ · ~~live regeneration of the
  5 seeds + gate targets~~ ✅ (this session).
- **Eval metrics on the regenerated set** — `grade_material_grounding.py` /
  `grade_material_difficulty.py` produce the gate verdicts (done via the sweep), but the
  reference-based scores are **not yet run** on the new material: `split_references_by_difficulty.py`
  → tier-matched `run_multi_reference_eval.py` (BERTScore), `run_material_eval.py` (BLEU/ROUGE),
  `run_llm_judge.py`. Target: F1 within noise of 0.840.
- **PDF compile** (needs texlive), **full Flutter build/run**, deck edit (deck not in this repo).
- **A-B vs `job_477df73f`** (old) — title drift, "fan blade on fan blade", advanced≈intermediate
  should all be gone (spot-confirmed by the sweep, not yet a formal side-by-side).

## Cloud-model experiment (Xiaomi MiMo) + what it taught us about the gate and the 35B limit — 2026-07-08

**Context.** Qwen-205 (the local `Qwen3.6-35B` the material stage normally calls) was down, so we
tested a cloud model — **Xiaomi MiMo** (`https://token-plan-sgp.xiaomimimo.com/v1`, OpenAI protocol,
key in `.env` `XIAOMI_API_KEY`) — as a drop-in for the material stage, and used it to re-attempt the
two gate-failing jobs from the E2E sweep (turntable-3 = arithmetic fail, roundabout-4046 = motion-desc
fail). The material stage is swappable by env alone: `material_tiers.py` reads `PI_INFERENCE_URL` +
`PI_INFERENCE_API_KEY` + `PI_MATERIAL_MODEL` and POSTs `/v1/chat/completions` directly (no SDK). Run
`python -m analysis.material_tiers` in-container with those 3 vars overridden.

**Models.** `mimo-v2.5` is VISION-capable (read a real annotated turntable frame + OCR'd the
"r = 0.148 m" overlay); `mimo-v2.5-pro` is TEXT-ONLY (404 on image input); plus dedicated `-asr` /
`-tts*`. No single omni chat model. Both are reasoning models. **mimo-v2.5-pro is impractically slow**
for this pipeline: ~2 min/tier and up to **9 min for one advanced call** — a 3-tier run is 15+ min, a
regen loop 20+ min more, and it burns the token plan.

**The key result: testing a stronger model exposed that the GATE, not the model, was the main
blocker.** MiMo gets the physics *more* right than Qwen (e.g. computes `a_c = 57.9·0.148 = 8.57`
correctly, where Qwen dropped the `·r` and wrote "= 57.9"), but its *fuller, more pedagogical*
derivations tripped three gate weaknesses:
1. **Arithmetic false-positive** on chained equations. A worked solution that restates the
   intermediate — `(7.609)² · 0.148 = 57.9 · 0.148 = 8.57` — was misread by the squared-form regex as
   the claim `7.609²·0.148 = 57.9` (wrong) and false-failed correct math, trapping regeneration in an
   **infinite loop** (model keeps writing correct physics, gate keeps rejecting). → FIXED (`NOCONT`
   guard: a result immediately followed by another operator is a restated intermediate, not a final
   claim; `(?![.\d])` blocks the engine backtracking 57.9→57 to dodge the guard).
2. **Over-strict number-grounding** on the advanced tier. MiMo derives `T = 2π/ω` at real seed ω
   instants and the `a_c ∝ ω²` scaling ("ω drops by 2.40 → a_c drops 2.40²=5.76") — physics the
   advanced tier's own spec *asks for* — but `allowed_values` only sanctioned a fixed derivation set,
   so these read as fabricated. → FIXED (sanction `T=2π/ω`, `f=ω/2π` at any grounded ω, and meaningful
   ω-ratio / a_c-ratio; ratios within 0.05 of 1.0 excluded so a fabricated `R²=0.99976` stays
   correctly ungrounded, paired with a hint that fit quality is qualitative — never cite an R²).
3. **Total-swept-angle** ungrounded (roundabout basic: "four full turns, ~1340°"). → LEFT OPEN, on
   purpose: the seed is internally inconsistent here (`active_duration_s=15` yet 360° is crossed at
   t=0.68 s; ½(ω₀+ω_f)·dur ⇒ ~6695°/18 turns, not 1340°/4 turns), so MiMo's 1340 may be a genuine
   miscalc OR the seed numbers are wrong. Needs a **data-integrity check**, not a reflexive gate
   widening.

Fixes 1–2 are committed on branch `fix/material-gate-arithmetic-grounding` (`10281bc`, not merged;
`material_gate.py` + `material_hints.md` + `test_material_gate.py`, 10/10 tests). With them, MiMo's
turntable-3 basic+intermediate pass clean with no regen loop, and its advanced derived numbers ground
offline (R² correctly still flagged). roundabout-4046 was stopped mid-run at the user's request.

### The 35B limitation, deepened

The earlier framing was one-sided: "Qwen-35B drafts well but self-corrects poorly on regen." This
experiment sharpens it into a **two-sided** picture, and it means a Qwen re-run of the failing jobs is
**not expected to fix them reliably**:

- **Qwen's gate failures were REAL physics/faithfulness errors, not gate false-positives.** turntable-3
  = a genuine miscalc (dropped `·r`); roundabout-4046 = a genuine faithfulness slip ("constant rate"
  for a decelerating clip). The gate caught both correctly. None of the gate fixes above make a wrong
  answer right — they only stop *correct* elaborate derivations (MiMo's) from being false-failed. Qwen's
  terser style rarely even triggers those false-positives, so the fixes are largely **neutral** for it.
- **These fault classes are stochastic** (the sweeps already showed turntable-3 pass→fail and
  roundabout-4048 fail→pass across runs). So a Qwen re-run is a coin-flip per fault, and its poor
  regen self-correction (re-emits the same error / trades one violation for another) means the
  regen budget won't converge it either.
- **Net:** the ceiling on Qwen here is not the gate — it's the model's own accuracy + inability to
  fix itself when told what's wrong. The durable levers remain (a) **first-pass steering** via
  `material_hints.md` (works because the first draft is the reliable one), and (b) a
  **generate-K-then-select** loop or a stronger model (cf. Utami's SocioMathLLM CoT candidate
  selection). MiMo shows a stronger model does raise the physics ceiling — but it is too slow here,
  and *revealed the gate needed hardening before any model comparison is fair*.

**Practical follow-ups:** to measure a Qwen re-run honestly, run it a *few times per job* and report a
pass **rate**, not a single verdict (it is stochastic). The remaining gate item (total-angle) is
blocked on a seed data-integrity check for the roundabout family, not on a gate change. Ops notes for
the swap: always launch the in-container run with `docker exec -d` (a foreground exec that "times out"
keeps running and races on the same files); `pkill -f material_tiers` self-kills its own shell — use
the bracket trick `pkill -9 -f "[m]aterial_tiers"`; per-job workspaces carry a stale `analysis/` copy,
so `cp` the fixed `material_gate.py`/`material_hints.md` into `workspaces/job_*/analysis/` before
re-running that job.
