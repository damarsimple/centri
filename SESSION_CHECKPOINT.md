# Session Checkpoint — 2026-07-15 (video DATA QUALITY: tracking + projective artifacts)

Single source of truth to resume after a context reset. **Compacted 2026-07-15** — completed work
was removed; it lives in `git log -p SESSION_CHECKPOINT.md` (full pre-compact text at `HEAD`),
the memory files (`~/.claude/projects/-home-damar-centri/memory/centri-*.md`), and the docs cited
below. Keep this file short: current state, open work, ops crib — not a diary.

## 00. RESUME HERE — 2026-07-16 (fan scale MEASURED → v/a_c gold; ω(t) staircase fixed; 1 ruler left)

Prof steered off pedagogy back to **data quality** (P-MAGIC's ω curve is a clean line, ours is
jagged). Full evidence + every number: **`agent-backend/docs/tracking-data-quality-2026-07-15.md`**.
Paper-style writeup: **`technical-report/centri-video-data-quality.tex`** (19 pp, compiles clean,
10 figures in `technical-report/figures/`). Per-clip guidance: **`agent-backend/templates/*/hints.md`**
(all 10). Archived clip + re-shoot spec: **`agent-backend/templates-reshoot/README.md`**.
Memory: [[centri-tracking-data-quality]] (+ correction to [[centri-detection-prompt-wording]]).

**TRUSTED SET = 4 phenomena / 7 clips.** Two tiers:
- **GOLD** = the per-frame *trajectory* is measured; every quantity is a direct observation.
- **SILVER** = the *rate* and *scale* are measured, so ω/T/f/v/a_c are trustworthy and teachable,
  but the per-frame *trajectory* is **reconstructed from the rate** (no resolvable point) — present
  the orbit as a model, never as measured data. ("Gold numbers, reconstructed picture.")

| # | phenomenon | tier | how |
|---|---|---|---|
| 1 | roundabout-4046 | GOLD | **rectified** — the only clip with real perspective |
| 2 | turntable (t-1/2/3, = flick) | GOLD | as-is (per-frame marker) |
| 3 | computerfan-4029 | GOLD | as-is (per-frame red marker) — our own gate had falsely condemned it |
| 4 | ceiling fan (4027+4028) | **SILVER** | scale MEASURED (ruler 07-16) → px_per_m 559; v/a_c at blade tip; ω(t) sub-bin-smoothed. Rate+scale gold, orbit synthesized |
**Only #1 needed the DATA corrected**; the rest were won by fixing our diagnostics/config.

**THE RULE: perspective strength = HUB OFFSET (imaged axle ↔ centre of the elliptical path), NOT
tilt.** 4046 = 85.6px; every other clip 0.7–8.8px. Rectifying the others does nothing — correctly.
An earlier "perspective is systematic" claim is **RETRACTED** (classifier read the A1/A2 ratio
without checking phase-lock).

**DONE 07-16 — fan scale + ω(t) staircase (commit on `feat/video-annotation-phase-labeller`):**
- **Ruler:** hub→blade-tip = **63.5 cm (25″)**, blade = 20″. Blade tip = 355 px (sd 0.5) →
  **px_per_m = 559** (retires the provisional 0.6 m = 425 guess). Sidecars 4027/4028 now
  `orbit_radius_px 355` / `physical_size 0.635`; `reference.label` = "blade-tip orbit".
- **Report radius = BLADE TIP** (student-natural max; ω rigid-body so v_tip=ω·r_tip is exact,
  not extrapolation — in freq mode ω comes from the blade-pass FFT, not the marker). Peaks:
  4027 v≈2.68 m/s / a_c≈**11.3 m/s² (1.15 g)**; 4028 v≈7.36 / a_c≈**85.2 (8.69 g)**. The marker
  itself orbits at ~49 cm (inboard); the optional `tracking_mode: color` flip is NOT needed for v/a_c.
- **ω(t) staircase KILLED** — was FFT-bin quantization (steps of 2π·(1/2.5s)/5 ≈ 0.5 rad/s), a
  method artifact (only freq-mode; 4029/flick per-frame come out smooth). Fix =
  `freq_track._peak_hz_parabolic` sub-bin peak interp. Confirmed via real `analysis.run`
  (px_per_m 559, r 0.635) + tests 33/33. Figs: `docs/figures/{ac_t_fans,omega_method_compare}.png`.
  (Vinsa/student-POV: a staircase reads as "constant speed then jumps" — confusing; smoothed.)

**OPEN (needs Damar, do NOT guess):**
1. **Ruler on the phone body** (NOT the 5.5" screen diagonal) + confirm the wheel → settles
   bicycle's 12% scale cross-check (phone→tire gives 58.6cm vs a real 66–70cm wheel ⇒ one
   reference is wrong; suspect the spokes clip the phone's mask).
2. **bicycle stays OPEN** — phase-lock 0.72 that is NOT perspective (4.9px), NOT occlusion
   (area-vs-phase R²=0.07), gravity has right sign but wrong phase (138° off). Cause unknown.
3. **Decide:** implement rectification in `geometry.py` gated on a new `hub_px` field in
   `pipeline_inputs.json` (agent detects the axle in Step 5). A hint CANNOT do this — `analysis/`
   is FROZEN by the orchestrator's hard rules, and an e2e proved the agent correctly refuses.
   **Rectifying 4046 WILL move its golden numbers** (the old ones were wrong).
4. `color_track.py` bugs worth fixing regardless: `area × mean_saturation` is invalid for a DARK
   target; `max_step` must come from `ω·r/fps`, not a round number.

**SHIPPED THIS SESSION (uncommitted, working tree):** `worker/tasks.py` `_inject_clip_hints()` +
`{{CLIP_HINTS}}` in `prompts/orchestrator.txt` (hints are **injected into the prompt**, verified
live — telling the agent to "read hints.md" fails: it logged "hints.md found — AUTHORITATIVE" and
never read a word). 4048 moved to `templates-reshoot/`. 10 × `hints.md`. Report + evidence doc.

**METHOD LESSON (cost 4 wrong claims):** overlay the cached track on REAL frames before trusting
ANY statistic. Killed: "4048 is at 29° tilt" (a conic fitted to trees), "squash the ellipse"
(right about the ellipse, wrong remedy), "perspective is systematic", "4029 is contaminated".
**Coverage ≠ correctness** (4048 reports 1.0 while ~38% wrong; 4031 reports 100% tracking a
motion-blur smear).

---

## 00b. 2026-07-14 — material-quality backlog (DONE; kept only as a pointer)

Critique of `e6fed2e9` vs P-MAGIC → `agent-backend/docs/material-pedagogy-critique-2026-07-14.md`
(Part A correctness, B design, C multimodal).

**The ENTIRE correctness/annotation backlog (A1–A8, C1–C5) + agreed Part-B items are DONE,
committed and live-validated** on branch `feat/video-annotation-phase-labeller` (23 commits ahead
of main, PR #1 open + mergeable, tests 33/33). Golden = **`9ed918d0`** (int+adv gate CLEAN; basic
only the known stochastic vocab/`²` leak). Per-item detail, commit hashes and the new deterministic
gates (`wrong_duration_products`, `average_period_as_peak`, `_phase_significant`,
render-aware `annotation_issues` `2c24a0d`) live in **[[centri-tiered-material]]** +
**[[centri-annotation-reorder-progress]]** and `git log -p`.

**REMAINING (design/pedagogy only, not correctness):** A7 two-scenario contrast, per-phase
colour-coded table (C4 upgrade), predict-box, contextualize/noticing/anchor, Bahasa. See the
critique doc §Part B.

## 1. Current state & in-flight (as of 2026-07-15)
- **Branch `feat/video-annotation-phase-labeller`, PR #1 OPEN + MERGEABLE**
  (https://github.com/damarsimple/centri/pull/1), **23 commits ahead of main**, unmerged.
- **Stack:** lab2 API/worker/redis UP (`docker compose -f docker-compose.yml -f compose.lab2.yml up
  -d api worker redis`, API `10.0.0.2:8088`); Qwen3.6-35B `192.168.1.205:8083` UP;
  **SAM3 `10.0.0.1:8086` is UP** (verified 07-15; tracked 5 clips + prompt sweeps). If it dies again:
  a `prompt_sweep.py --reset` POSTs `/reset` which EXITS the server and `run_sam3.sh` doesn't relaunch;
  source `/home/damar/sams2/sam3cpp/api_master_sam3.py`. **API key is `changeme-random-secret-key-12345`**
  (`.env` `API_KEY`, NOT `PI_INFERENCE_API_KEY`); `/analyze` needs `;type=video/mp4` on the -F upload.
- **Golden validation job:** flick **`9ed918d0`** (regen 2026-07-14, ALL fixes incl. A6 authentic story
  + misconception + CYU→teacher + A8.2 precision + (avg) chips; done 100%; int+adv gate CLEAN, basic
  only the stochastic vocab/`²` leak). Its figures/material are referenced ON the weekly deck for a live
  walk-through. Prior golden `fa790a23` = A1–A5 only; `5e41d8d9` = A1+C1+restyle; `e6fed2e9` = pre-fix.
  Template `templates/base-template-flick/` (sidecar now carries `scene_context` for A6) + `api_cache.json`
  → cache HIT, no re-track; worker volume-mounts `./workspace_lib` so host edits are live (no rebuild).
  Re-submit crib: POST /analyze with `input_video.mp4` (any flick workspace) + `-F template=base-template-flick`.
- **Weekly deck:** NEW `presentation/centri-weekly-2026-07-15.tex` COMMITTED (`aa8e33e`) — standalone,
  6 slides (material-quality + multimodal annotation, current-state). **CLAUDE.md now has a 5th deck
  rule — STANDALONE/self-explanatory** (committed `865b76c`; see [[centri-presentation-style]]).
- **UNCOMMITTED (working tree):** the 07-15 data-quality workstream (see §00: `worker/tasks.py`,
  `prompts/orchestrator.txt`, 10 × `templates/*/hints.md`, `templates-reshoot/`, `docs/figures/`,
  `docs/tracking-data-quality-2026-07-15.md`, `technical-report/`) + the prior-session
  eval-framework workstream + `docs/material-pedagogy-critique-2026-07-14.md` + `compose.lab2.yml`
  + `document-4.pdf` + this checkpoint. **Nothing from 07-15 is committed yet.** Eval files:
  `docs/{eval-framework,eval-progress,eval-rubric-ika,related-work-positioning,effectiveness-study-blueprint}.md`,
  `tools/{run_llm_judge,build_rater_sheet,eval_stats,generate_tier_material}.py`.

## 2. Who & what / goal
- **Damar** (MSc, builds Centri) · **Vinsa** (labmate/team leader, P-MAGIC author side, owns
  evaluation, physics-teaching background, Bahasa) · **Prof. Wu-Yuin Hwang** (advisor).
- **Centri** = video CV tracking (not IMU) → kinematics → seeded 3-tier learning material +
  multimodal annotation; FastAPI+Celery+Redis (Docker), `pi` agent CLI, local Qwen3.6-35B.
  P-MAGIC (`document-4.pdf`) = sibling app (GPT-4o + phone sensors, 3-level multimodal problems,
  BERT/STS/LSTM + 10-teacher eval). Parent line = Ika Utami's dissertation (SocioMathLLM, Geo-QG).
- **Goal:** comparable evaluation / joint paper. Paper 1 = video-vs-sensor validity +
  material-quality eval; Paper 2 = learning study (`PAPER2_LEARNING_STUDY.md`).
- Thesis contribution = video-based generation + multimodal annotation; eval Axes 1–4 in
  `docs/eval-framework.md` (Axis 4 = annotation correctness / multimodal).

## 3. Parked / older open items (still live, low priority)
- **BLEU/ROUGE decision pending** — if run, expect LOW (lexical vs paraphrase) and frame as
  motivating BERTScore; `pip install sacrebleu rouge-score` into `.venv-eval`.
- **IMG_3750 fan (prof's recapture):** freq job `1c183872` verified good (two-phase, peak ω≈3.5);
  **physical scale PROVISIONAL 0.6 m** — rescale when blade-tip orbit measured; object job
  `8d95a817` is the BROKEN ROI run (do not use). Single-regime classifier mislabels two-phase
  `motion_type` — extending it is roadmap; faithful ω(t) lives in `frequency_meta.json`.
- **Questions module (Subagent C) is GATED OFF** by default (`report.py RENDER_QUESTIONS`,
  env `PI_RENDER_QUESTIONS`); re-enable for a P-MAGIC question comparison.
- Deck consolidation (fold `centri-cases-eval.tex` into main deck?) undecided; deck rules =
  repo `CLAUDE.md` + [[centri-presentation-style]].
- `/suggest-scene` + AnnotateScreen should emit simple-noun cues (prompt-wording lesson).
- Multilingual eval parked (English-only official; 23-PDF multilingual + 18-PDF English reference
  sets live under `material_work/_reference/` with READMEs).

## 4. Ops quick-reference
- **Submit job:** `POST 10.0.0.2:8088/analyze` `-F "video=@f;type=video/mp4" -F "sidecar=$(cat
  sc.json)"`, header `X-API-Key: $(grep ^API_KEY= agent-backend/.env|cut -d= -f2)` (octet-stream
  rejected). **Re-enqueue:** `docker compose exec -T -w /app worker python -c "from worker.tasks
  import run_pi_analysis; run_pi_analysis.delay('<job_id>')"` (idempotent — runs only missing artifacts).
- **Workspaces carry a STALE `analysis/` copy** (seeded at job creation, root-owned): `cp` fixed
  `workspace_lib/analysis/*` into `workspaces/job_*/analysis/` (inside the worker container) before
  re-running a stage; `rm -rf analysis/render/__pycache__` first (stale .pyc served old code once).
  New jobs via `POST /analyze` reseed from CURRENT workspace_lib.
- **Deterministic PDF recovery** (after runaway-guard fails at report): `docker compose exec worker …
  python -m analysis.render.report` in the workspace, then `pdflatex ×2` (teacher key needs
  **lualatex** for ✓). Qwen is reachable from the WORKER container, not the host sandbox.
- **Worker kills:** `celery revoke --terminate` stalls the prefork pool → `docker compose restart
  worker`; a DELETEd job's pi process keeps running (kill the `pi` PID in-container);
  `pkill -9 -f "[m]aterial_tiers"` (bracket trick — plain pattern self-kills); long in-container
  runs: launch `docker exec -d` (foreground “timeout” leaves orphans racing on files).
- **`cleanup_expired_workspaces` (hourly) + job deletion REMOVE workspaces** — export promptly.
- Calibration `px_per_m = reference.diameter_px / physical_size_m`. zsh: `status` is read-only.
- Detection cues = simple nouns (`docs/object-detection-prompts.md`); `tools/prompt_sweep.py` ranks
  cues on a short clip (`--reset` kills SAM3 — leave OFF).

## 5. File map (pointers)
- **Data quality (07-15):** evidence + every number `agent-backend/docs/tracking-data-quality-2026-07-15.md`;
  report `technical-report/centri-video-data-quality.tex` (+`.pdf`, `figures/`); working rectification
  prototype `agent-backend/docs/figures/rectify_prototype.py`; per-clip guidance
  `agent-backend/templates/*/hints.md` (10); archived clip + re-shoot spec
  `agent-backend/templates-reshoot/README.md`; hint injection `worker/tasks.py:_inject_clip_hints()`
  + `{{CLIP_HINTS}}` in `prompts/orchestrator.txt`.
- **Material pipeline:** `workspace_lib/analysis/{material_seed,material_tiers,material_gate,
  quality_signals}.py`, `render/{report,figures,annotate}.py`, hints `analysis/material_hints.md`,
  spec `docs/difficulty-tiered-material-spec.md`, orchestrator `prompts/orchestrator.txt`.
- **Eval:** `tools/{run_material_eval,run_multimodal_eval,run_multi_reference_eval,
  run_reference_comparison_eval,grade_material_grounding,grade_material_difficulty,run_llm_judge,
  build_rater_sheet,eval_stats}.py` (`.venv-eval`); references + reports under `material_work/`;
  framework docs `agent-backend/docs/eval-*.md`; **critique
  `docs/material-pedagogy-critique-2026-07-14.md`**.
- **Decks:** `presentation/centri-end-to-end.tex` (advisor), `centri-cases-eval.tex` (focused),
  weeklies `centri-weekly-*.tex` (latest `2026-07-15` = material-quality+annotation, standalone) —
  **5 treatment rules** in repo `CLAUDE.md` (rule #5 = standalone/self-explanatory).
- **Research docs:** `PAPER_GAP_ASSESSMENT.md`, `PAPER2_LEARNING_STUDY.md`, `document-3.pdf`
  (P-MAGIC preprint), `document-4.pdf` (P-MAGIC journal), notes `note-*`.
- **Export:** `agent-backend/vinsa_export/` (validation-centric, `tools/build_vinsa_package.py`).
- **Trackers:** SAM3-CPP prod `/home/damar/sams2/sam3cpp/` (`api_master_sam3.py`, `run_sam3.sh`);
  LA experiment `test/locateanything_worker.py` (:8087, DOWN; slow — not adopted).
- **Memory files** (cross-session context): `centri-{tiered-material,annotation-reorder-progress,
  e2e-run-plan,eval-plan,eval-multimodal-pivot,thesis-contribution-titles,pmagic-alignment,
  utami-dissertation,second-pc-lab2,sam3-chunk-fix,detection-prompt-wording,
  kinematics-center-and-spinup,video-literature-review,presentation-style,deck-axis-terminology,
  tracking-data-quality,checkpoint-hygiene,team-pedagogy-gap}.md`.
