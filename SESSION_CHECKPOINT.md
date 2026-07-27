# Session Checkpoint — 2026-07-27 (the tiered material is reworked, checked, and live-validated)

Single source of truth to resume after a context reset. **Compacted 2026-07-27** (was 663 lines) —
completed work was removed; it lives in `git log -p SESSION_CHECKPOINT.md`, the memory files
(`~/.claude/projects/-home-damar-centri/memory/centri-*.md`), and the docs cited below. Keep this
file short: current state, open work, ops crib — not a diary.

---

## 00. RESUME HERE — state on stopping, 2026-07-27

Everything is **committed and pushed** (`main` = `origin/main` = `9d72e55`). Working tree clean.
Tests green: gate 34/34, kinematics motion 7/7, rectify 9/9, phases 8/8, quality 7/7, contract 7/7,
dropped-frames + direction pass.

**Qwen3.6-35B is UP** at `192.168.1.205:8083` and was used all session. The 7-clip material sweep
ran twice end to end; the second run is what the numbers below describe.

### What landed this session
The 07-23 pedagogy plan (`agent-backend/docs/material-pedagogy-plan-2026-07-23.md`) is **built in
full**, plus a second pass answering a pedagogical audit of the result:

- **The direction-sign defect is fixed.** `motion_type` came off `sign(alpha)`; both ceiling-fan
  clips turn the way the tracker calls negative, so a coast-down fitted α = +0.17 and one BASIC
  worksheet taught *"speeding up motion"* over a graph reading "slowing down".
  `kinematics.alpha_along_rad_s2` = d|ω|/dt decides it now, and `common.motion_along_travel(stats)`
  is the ONE reader-facing view (α along travel, a_t signed against motion, endpoint ω as SPEEDS).
  It back-derives from the ω endpoints, so an archived `stats.json` renders correctly. Exactly 2 of
  7 clips flip.
- **Reading level, order, staircase**: rule 8c bans calibration / scale-free / Jensen / ⟨·⟩ with the
  formal version re-routed to a teacher-copy-only `teacher_notes` block; intermediate reads the
  graph before the equation (`SECTIONS_INTERMEDIATE` + `report._material_order` — do not let those
  drift); `TIER_STEPS` gives three graded steps per level, each ending in a checkpoint rendered
  where the step really ends, with bridges naming the next step.
- **Figures**: basic gets the same four-arrow frame as the other tiers via
  `fig_annotated_image(plain=True)`, labelled in words; a rectified clip carries `*_uncorrected`
  CSV columns so ω(t) and a_c(t) draw the measurement AND the correction.
- **The reader now does something** (second pass): predict-before-the-reveal, step checkpoints,
  the documented misconceptions, a transfer prompt, self-placement, and faded worked examples at
  advanced. All deterministic; every answer held for the teacher copy.

### Numbers that are current
- **21 of 21 worksheets pass every check** across the 7 trusted clips (one residual cross-tier
  note on computerfan-4029: its intermediate reuses another tier's instant — a distinctness rule,
  not a wrong number).
- **Element interactivity rises 7/7 clips**: 5 → 19 → 44 (mean).
- **Readability**: basic went 15.8 → 8.2 words/sentence, FK 7.2 → 4.3. Advanced is now the hardest
  of the three on both. They are still NOT strictly ordered by reading grade (intermediate reads
  easiest) — do not claim monotonic.

### ⚠ Two claims RETRACTED this session — do not quote the old ones
1. **The 07-23 plan deck's "reading grade 7.8 / 8.1 / 11.7" does not hold** and is not repeated.
   Measured on the trusted set the FK ladder rose on 0/7 clips. Report FK; do not optimise it.
2. **`presentation/figs/mk_corrected_ac_fig.py` overstates the correction.** Its "before" comes
   from the archived pre-coordfix run, so it also carries the 232 px coordinate bug (peak ~60
   m/s²). The shipped figure isolates the camera angle alone: swing 7.8–31.8 → 9.8–23.0, mean
   essentially unmoved (16.2 → 16.1).

### ⚠ Still binding from 07-21 — read before quoting any ripple number
- **Cross-tracker agreement figures were inflated by the at-rest tail.** Honest values on the 79
  shared ACTIVE frames: ripple correlation **r = +0.81 (not 0.98)**, mean-ω agreement **1.7% (not
  0.10%)**. Any agreement statistic must exclude the dead segment.
- **turntable-3's ripple is NOT demonstrably phase-locked.** No clip in the corpus beats its own
  surrogate null; on a 1.5-revolution clip the statistic invents 20–30% of variance from noise, and
  the shipped `PHASELOCK_UNRELIABLE = 0.60` has a **5.2% false-positive rate**. 4046's
  pre-rectification 0.94 over 18.6 revs *is* real. Recommended, not built: per-clip surrogate test
  instead of the constant.
- **turntable-3's mid-coast speed-up is an artifact, cause unidentified** — it joins `bicycle` in
  that bucket. Ruled out: marker centroid, motion blur, perspective, wrong centre, real torque, and
  SAM3's masks specifically (LocateAnything-3B reproduces it).
- **The accuracy limit is the MARKER, not the projection model.** The next real gain is a small
  flat high-contrast sticker — camera work, not mathematics.

---

## 1. Open work

**Teaching (needs people, not code)**
- **Teacher ratings.** The only thing that answers "does this teach?". Everything measured so far is
  a property of the text. P-MAGIC has 10 teachers at 8.2–8.6/10; Centri has one expert reader.
- **Should the no-forces rule (gate rule 8b) stay?** It keeps every claim inside what the video
  measures, and it puts the commonest circular-motion misconceptions out of reach.
- **Are the three steps the right three?** The staircase is built and climbable; its shape is a
  teaching judgement.
- **Bahasa Indonesia edition** (`tools/translate_material.py` exists, unwired).

**Measurement / model**
- **A stronger writer or a select-from-K loop.** The one remaining failure class is the local 35B
  repeating a banned word when told to fix it. Durable lever stays first-pass steering via
  `analysis/material_hints.md`.
- **Re-film two clips** with a flat high-contrast sticker; **a ruler in every scene** (real-world
  size is the weakest link in two clips).
- **Ceiling fan with sensors** — `IMG_3075.csv` is the phone accel/gyro trace for this; the video
  half is not yet shot. This is the video-vs-sensor comparison the thesis wants.
- **One unexplained clip** (bicycle) — repeating wobble that is not the camera angle.

**Known, low priority**
- `PHASELOCK_UNRELIABLE` should become a per-clip surrogate test (see above).
- The park wheel waits in `templates-reshoot/base-template-parkwheel-4091/` — no validated tracker
  follows it yet, however good the footage.

---

## 2. Who & what / goal

MSc thesis, Hwang lab. **Centri** = phone video of circular motion → measured kinematics → tiered
physics worksheets with annotated figures. Sibling app **P-MAGIC** does the same from phone
*sensors*; the parent line is the **Utami dissertation** (SocioMathLLM, Geo-QG). The contribution is
video-based generation plus multimodal annotation, and the honesty layer around the measurement.

---

## 3. Ops quick-reference
- **Submit job:** `POST 10.0.0.2:8088/analyze` `-F "video=@f;type=video/mp4" -F "sidecar=$(cat
  sc.json)"`, header `X-API-Key: $(grep ^API_KEY= agent-backend/.env|cut -d= -f2)` (octet-stream
  rejected). **Re-enqueue:** `docker compose exec -T -w /app worker python -c "from worker.tasks
  import run_pi_analysis; run_pi_analysis.delay('<job_id>')"` (idempotent).
- **Workspaces carry a STALE `analysis/` copy** (seeded at job creation, root-owned): `cp` fixed
  `workspace_lib/analysis/*` into `workspaces/job_*/analysis/` before re-running a stage;
  `rm -rf analysis/render/__pycache__` first. New jobs via `POST /analyze` reseed from current
  `workspace_lib`.
- **TAIL REPLAY — test a material/figure change with no agent and no SAM3 (~5 min).** Clone a
  workspace with a good `pipeline_inputs.json`, drop in current code, run the deterministic steps.
  The worker mounts workspaces at the HOST path (`/home/damar/centri/agent-backend/workspaces`):
  ```
  W=/home/damar/centri/agent-backend/workspaces
  docker compose exec -T worker bash -c "cp -a $W/job_X $W/job_X-r2 && rm -rf $W/job_X-r2/analysis \
    && cp -a /app/workspace_lib/analysis $W/job_X-r2/analysis \
    && find $W/job_X-r2/analysis -name __pycache__ -exec rm -rf {} +"
  docker compose exec -T -w $W/job_X-r2 worker bash -c 'python -m analysis.run && \
    python -m analysis.render.figures && python -m analysis.material_tiers && python -m analysis.render.report'
  ```
  **Offline variant used all this session** (no Docker at all): copy `analysis_output` + current
  `workspace_lib/analysis` into a scratch dir and run `python3 -m analysis.material_seed`,
  `analysis.render.figures`, `analysis.render.report`, `analysis.material_tiers` in it.
- **A full e2e re-run of 4046 is not free:** it died on the 1024 MB runaway guard in the track phase
  (the injected hints send the agent prototyping rectification). Prefer the tail replay for
  material work; keep e2e for perception changes.
- **Worker kills:** `celery revoke --terminate` stalls the prefork pool → `docker compose restart
  worker`; `pkill -9 -f "[m]aterial_tiers"` (bracket trick — a plain pattern self-kills); long
  in-container runs: launch `docker exec -d` (a foreground "timeout" leaves orphans racing on files).
- **`cleanup_expired_workspaces` (hourly) + job deletion REMOVE workspaces** — export promptly.
- Calibration `px_per_m = reference.diameter_px / physical_size_m` — **the two must describe the
  SAME span**; in `frequency` mode both are RADII despite the field name. zsh: `status` is read-only.
- Detection cues = simple nouns (`docs/object-detection-prompts.md`); `tools/prompt_sweep.py` ranks
  cues on a short clip (`--reset` kills SAM3 — leave OFF).

---

## 4. File map (pointers)
- **Material pipeline:** `workspace_lib/analysis/{material_seed,material_tiers,material_gate,
  kinematics,common,quality_signals}.py`, `render/{report,figures,annotate}.py`, first-pass steering
  `analysis/material_hints.md`, spec `docs/difficulty-tiered-material-spec.md`, orchestrator
  `prompts/orchestrator.txt`. Pedagogy plan + status:
  `docs/material-pedagogy-plan-2026-07-23.md`; earlier critique
  `docs/material-pedagogy-critique-2026-07-14.md`.
- **Tests** (all offline, no LLM): `agent-backend/tools/tests/test_*.py`. `test_material_gate.py` is
  the big one and pins every gate rule including the four "the pipeline asked for what its own gate
  refuses" fixes.
- **Data quality (07-15/07-21):** evidence `agent-backend/docs/tracking-data-quality-2026-07-15.md`;
  report `technical-report/centri-video-data-quality.tex`; per-clip guidance
  `agent-backend/templates/*/hints.md`; re-shoot spec `agent-backend/templates-reshoot/README.md`;
  ablation `ABLATION_METHOD_STUDIES.md`.
- **Eval:** `tools/{run_material_eval,run_multi_reference_eval,grade_material_grounding,
  grade_material_difficulty,run_llm_judge,build_rater_sheet,eval_stats}.py` (`.venv-eval`);
  framework docs `agent-backend/docs/eval-*.md`.
- **Decks:** weeklies `presentation/centri-weekly-*.tex` (latest `2026-07-27`); general-audience
  overview `centri-talk-intro-2026-07-27.tex`; plan deck `centri-plan-2026-07-23.tex` (never
  presented). **6 treatment rules in repo `CLAUDE.md`** — they govern WEEKLIES; the talk deck
  departs from rule #5 on purpose and says so in its header. Figure generators live beside the
  figures (`presentation/figs/mk_*.py`) because PNGs are gitignored.
- **Research docs:** `PAPER_GAP_ASSESSMENT.md`, `PAPER2_LEARNING_STUDY.md`, `refs/document-3.pdf`
  (P-MAGIC preprint), `refs/document-4.pdf` (P-MAGIC journal), notes `note-*`.
- **Trackers:** SAM3-CPP prod `/home/damar/sams2/sam3cpp/` (`api_master_sam3.py`, `run_sam3.sh`);
  LA experiment `test/locateanything_worker.py` (:8087, slow — not adopted).
- **Memory files** (cross-session context): `~/.claude/projects/-home-damar-centri/memory/` —
  `centri-{tiered-material,annotation-reorder-progress,e2e-run-plan,eval-plan,
  eval-multimodal-pivot,thesis-contribution-titles,pmagic-alignment,utami-dissertation,
  second-pc-lab2,sam3-chunk-fix,detection-prompt-wording,kinematics-center-and-spinup,
  video-literature-review,presentation-style,deck-axis-terminology,tracking-data-quality,
  checkpoint-hygiene,team-pedagogy-gap,phaselock-null,phaselock-trust-channel,dropped-frame-guard,
  coordinate-space-guard,locateanything-ablation,templates-gold-only}.md`.
