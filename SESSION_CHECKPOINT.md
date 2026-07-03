# Session Checkpoint — 2026-07-04 (refresh 13)

## 0. MOST RECENT — refresh 13 (playground oblique-capture + learning-material rework)
Driven by `note-1` (playground "black ball" job weird values) + a long live thread. **Nothing
committed.** All changes in `workspace_lib/` (source; new jobs inherit, existing workspaces need
the `analysis/` sync), `docs/`, `prompts/orchestrator.txt`, `templates/`. Scratch render +
prototypes in session scratchpad (`.../scratchpad/{qtest,render_pg}`).

1. **DEBUGGED playground job `c11267e1`** ("black ball" = a black **handle** on a playground
   arm-wheel). The ω(t) "weird oscillation" (±25%, CV 0.20) is a **viewing-angle projection
   artifact**, NOT physics and NOT a center bug: the circular orbit is filmed obliquely →
   image path is a tilted **ellipse** → apparent ω ripples **1×/rev, phase-locked** (radius
   2×/rev, ratio 1.13). Center is the correct fit; grid-search/ortho-deproject can't remove it
   (it's perspective). Real = mean ω 7.8, T 0.84 s, slow decel (α≈−0.2, the trend is real).
   Also: `T_fft`=14.998 s (whole clip) is garbage; `ransac_fit_rejected` is the pipeline
   correctly saying "not a circle".
2. **BUILT + wired a measurement-quality gate** (the non-hardcoded fix): NEW
   `workspace_lib/analysis/quality_signals.py` — general detector, **no clip-tuned constants**.
   Discriminator = is the ω residual (after removing the smooth time-trend) **phase-locked to
   orbital phase** (projection artifact) vs a real time-trend (accel/decel). Flags
   `per_instant_omega_unreliable` only on the **conjunction**: elliptical orbit (axis>1.08) AND
   phase-lock≥0.6 AND ripple-CV≥0.08. Validated across all 18 workspaces → **only c11267e1**
   flags (real-decel turntables with CV up to 0.42 correctly NOT flagged). `build_quality_block`
   → `measurement_quality` in the seed (`material_seed.py`).
3. **Agent policy + deterministic backstop.** `material_tiers.py`: `_quality_policy(seed)` injects
   a hedging rule when unreliable — forbid per-instant/timeline/ω(t)-shape/within-rev claims,
   **but PERMIT the whole-clip trend** (avoids over-hedge), strip the timeline from `_facts`,
   no per-instant a_c=ω²r verification. `_gate` is now **quality-aware** (skips the arithmetic-
   instant + advanced timeline/α checks when unreliable). Validated 4×/regression (earlier
   prototype: flagged→hedged 4/4, reliable→narrated, no over-hedge). Live result on the
   playground: all 3 tiers gate CLEAN, intermediate reads *"94% of that variation is locked to
   orbital phase … projection artifact … underlying physics is a smooth whole-clip deceleration."*
4. **Learning-material rework** (note-1 + "does it fit as learning material?"):
   - **Basic** now teaches angle-over-time (degrees/turn per second) + period, one idea at a
     time, qualitative "how related" (no numbers). **Intermediate** drops tangential speed
     (spec + core table + swapped v(t)→ω(t) graph), structured "arrow" relations.
     `docs/difficulty-tiered-material-spec.md` updated (Basic/Intermediate defs + §1 table +
     HARD CONSTRAINTS 11 learn-not-track / 12 plain-Unicode).
   - **`report.py`**: student edition = **clean learning material** (title "Circular Motion —
     Learning Material", minimal header, NO coverage/fps/Data-Quality/Questions); teacher key =
     material + Data-Quality (no questions). `a_c`/`a_t` render as real subscripts (filename-
     guarded); added `∝ ∞ ≡ ∴`; scene "X on X" de-duped.
   - **Plain-Unicode rule fixed the JSON parse failures** (LaTeX `$\omega$` → invalid escapes).
5. **Questions GATED OFF** (reversible, code kept): `report.py` `RENDER_QUESTIONS`
   (env `PI_RENDER_QUESTIONS`, default off); orchestrator Subagent C disabled by default, LaTeX
   gate no longer waits on `questions.json`. Re-enable for a P-MAGIC question comparison.
6. **Object relabel decoupled from tracking**: sidecar now carries `object_name`/`scene_title`
   (display) SEPARATE from `visual_cues` (SAM3 cue stays "black ball" — 100% coverage).
   Orchestrator Step 5 wires it; `templates/base-template-roundabout-4046/sidecar.json` set to
   "black handle" / "a black handle on a playground wheel". `figures.py` re-run picks up titles.
7. **GRAPH oscillation actually removed (not just described).** User pushed back — the ω(t)
   plot still showed the raw ripple. `figures.py` `_series_plot(smooth_trend=)` + `_smooth_1rev`
   (moving average over exactly one revolution → cancels the 1x/2x-per-rev ripple, keeps the
   real slow trend): on flagged clips ω(t)/a_c(t)/radius(t)/v(t) plot a **bold 1-rev trend over a
   faint raw trace**; peak-star suppressed on smoothed plots. **Gated on the same `unreliable`
   flag** (`report.py _is_unreliable`, `figures.py`), so only the playground smooths — fan/
   turntable/bike/etc. plot raw exactly as before (regression re-confirmed).
8. **Advanced-tier quality fixes** (it was contradicting itself): under `unreliable` the FULL
   measurements table **drops `max_ac`** (the ripple-peak artifact) — threaded `unreliable`
   through `_build→_material_block→_section_artifacts→_inline_table→_measurements_table`;
   advanced figure set **drops the `summary_panel` dump** (re-showed the rippled radius +
   duplicated the trajectory) → `TIER_ARTIFACTS` + the advanced tier's `figures` prompt updated
   in lockstep. Advanced 6 pp → **4 pp**.
9. **VERIFIED both regimes** (scratch renders, all compile + gate CLEAN):
   - Playground `c11267e1` (UNRELIABLE): basic 2 / int 3 / adv 4 pp — smoothed graphs, hedged
     prose that KEEPS the real coast-down trend, no per-instant peak/artifact. `.../scratchpad/render_pg/`.
   - Turntable `711fffe8` (RELIABLE decel): adv **fully narrates** — timeline instant t=2.72 s
     (v=ωr, a_c=ω²r verified exactly, Jensen-correct), α=−4.07, ω 9.93→2.13, limits analysis,
     keeps max_ac + peak-star, NO oblique caveat, NO smoothing. Confirms the gate only fires when
     it should. `.../scratchpad/render_turntable/`.
   Open trivia (cosmetic only): model writes "v_avg"/"ω_avg" → literal underscore; a_c table cell
   wraps "m/s²".
> **TO WIRE INTO A LIVE JOB**: sync edited `workspace_lib/analysis/*` (quality_signals.py NEW,
> material_seed.py, material_tiers.py, render/{report,figures}.py) + `prompts/orchestrator.txt`
> into a workspace's `analysis/` copy (root-owned, inside worker container), then re-enqueue.
> **COMMITTED** (refresh 13, branch `learning-material-oblique-gate`): the 9 files above +
> quality_signals.py + this checkpoint. Not merged to main; not yet run through a live job.

---

Single source of truth to resume after a context reset. Companions:
[PAPER_GAP_ASSESSMENT.md](PAPER_GAP_ASSESSMENT.md) (gap + to-do),
[PAPER2_LEARNING_STUDY.md](PAPER2_LEARNING_STUDY.md) (stage-2 plan),
[agent-backend/docs/object-detection-prompts.md](agent-backend/docs/object-detection-prompts.md)
(prompt-wording lesson), and memory files (`centri-*`).

---

## 1. Who & what
- **Damar** (you) — MSc student, building **Centri**.
- **Vinsa** — labmate / **team leader**; P-MAGIC author-side; owns evaluation. Bahasa.
- **Prof. Wu-Yuin Hwang** ("yuin") — advisor.
- **Paper**: `document-3.pdf` = P-MAGIC (GPT-4o + phone-IMU app, multimodal centripetal-
  acceleration problems, 3 difficulty levels, BERT/STS/LSTM + 10-teacher eval).
- **Centri** = superset: video CV tracking (not IMU) → kinematics → multimodal material +
  questions + Socratic tutor. FastAPI+Celery+Redis (Docker), `pi` agent CLI + seeded
  deterministic pipeline, local **Qwen3-35B** orchestration (lab requirement), Flutter app.

## 2. Goal
Align Centri with P-MAGIC for a comparable evaluation / joint paper. Paper 1 = video-vs-
sensor measurement validity + material-quality eval. Paper 2 = student learning study (see
PAPER2 doc). **Vinsa's weekend ask**: ~5 generated outputs across ≥2 objects so she can
build references and run BERTScore before Monday.

## 3. Done this session
1. Oriented (paper, backend outputs, Flutter flow). Gap assessment → `PAPER_GAP_ASSESSMENT.md`.
2. **Module C reworked** to P-MAGIC 3-tier (easy/intermediate/advanced) + modality tags;
   installed in all 3 def copies; **verified end-to-end** (job `cc9f02ce`: 12 q,
   {easy:6,int:4,adv:2}, 4 formats; `/result` worksheet populates; PDFs render). Also fixed
   a live bug (old bare-array `questions.json` was rejected by `load_worksheet`).
3. **Eval discussion**: BERT/STS/LSTM are reference-similarity, not quality; keep BERT for
   comparability, add **LLM-as-judge** later (parked). Built tooling + preliminary numbers.
4. **Built eval/export tooling** and ran preliminary auto-eval (turntable: BERT F1≈0.856,
   diversity≈0.62).
5. **LocateAnything tracker investigation** (see §5) — built LA `/track`, found the
   **prompt-wording lesson** (`"toy"` 100% vs `"cream colored doll"` 6%).
6. New docs: `PAPER2_LEARNING_STUDY.md`, `agent-backend/docs/object-detection-prompts.md`,
   `test/fan-tracking-findings.md`.

## 3b. Done THIS session (refresh 3)
1. **Re-ran bicycle** (`8110ab0d`) via production SAM3 → clean: coverage **93.8%**, period
   **1.18 s** (0.85 Hz), ω≈5.1 rad/s, a_c≈1.9–2.1 m/s². Exported.
2. **Cracked the fan tracking** (see §5): production tracker is **SAM3-CPP (GGML)**, NOT the
   YOLO-World python path. Prompt sweep on live `/track` → **`"yellow toy"`/`"hanging toy"`
   = 100%** (tracks the orbiting doll); single words = 0; `"fan blade"` = 100% but no orbit.
3. **Fan now runs end-to-end** with `"yellow toy"`: 5 s (`15948414`) then **7 s t=3–10
   (`a2627aa2`)** — both track doll 420/420 @100%. **BUT kinematics are noise-dominated**
   (doll orbit ~55 px, near hub): 5 s→period 3.77 s/ω 0.58; 7 s→period 1.04 s/ω 5.9 — 10×
   inconsistent. **Flagged for later investigation** (`radius_unstable`, `period_mismatch`,
   `high_center_drift`, `unstable_phase_linearity`, `center_mismatch`). User: leave data weird, fix later.
4. **vinsa_export now has 3 distinct objects**: turntable×3, bicycle, **fan (7 s `a2627aa2`)**.
   `_combined/` rebuilt; **auto_eval re-run** (n=59): BERTScore F1 **0.852**, combined
   diversity **0.611**, fan diversity 0.624; `references/` regenerated for all 5.
5. **Built advisor presentation**: `presentation/centri-end-to-end.tex` (+ `.pdf`), 21-page
   Beamer/metropolis deck, tuned for the prof (numbers + methods + pedagogy + statistics
   lead; infra/code light). Compiles `pdflatex` ×2. Removed 3rd-person "professor" phrasings.
6. Memory `centri-detection-prompt-wording.md` updated with the tracker-specific finding.

## 3d. Done THIS session (refresh 5) — MODULE D: LEARNING MATERIAL (the pivot)
**Vinsa's new ask (phone call):** she wants **material evaluation**, NOT question eval.
Focus everything on the **learning material (PDF)**; hide Q/A generation. Report as a
**table with mean ± SD**, autoeval number minimal. → We built grounded learning-material
generation end-to-end.

1. **Module D wired into the REAL pipeline** (sibling to Subagent C):
   - **Deterministic seed** `workspace_lib/analysis/material_seed.py` → writes
     `material_seed.json` (variables, formula relations, angular-acceleration block, and a
     time-anchored ω(t) from `kinematics.csv`). Called from `analysis/run.py` (Step 6).
   - **Subagent D** `.pi/agents/material-gen-subagent.md` — Qwen writes an authentic
     5-section passage (Scenario / Variables / Relationships / What the video shows over
     time / Reading the figures), grounded strictly on the seed (never invents numbers).
   - **Orchestrator** `prompts/orchestrator.txt` spawns D in the parallel wave; LaTeX gate
     waits for `material.json`.
   - **Render** `analysis/render/report.py` adds a **Learning Material** section leading
     the PDF (`_material_block`, reads `material.json`).
2. **Validated + requeued all 5 objects**: fan/bike/2 turntables ran the **real pipeline**
   (Subagent D → `material.json`); afe0f99f hit the runaway figure-loop guard on re-run, so
   its material was **recovered from its seed** via `tools/generate_material.py` (same
   prompt+model). All 5 reports re-rendered + recompiled → **Learning Material in every PDF**.
   > Re-enqueue is IDEMPOTENT — orchestrator runs only the *missing* artifact and skips
   > Step 6 + report regen. So: pre-run `analysis.run` (also adds the α block the turntables
   > lacked → all 3 now `decelerating`), re-enqueue for D, then deterministically re-render
   > the report. Workspace `analysis/` is a COPY → sync from `workspace_lib/analysis` inside
   > the worker container before requeue (root-owned).
3. **Reference = authentic textbook** (Vinsa's idea, user-supplied PDF): **OpenStax College
   Physics §6.2 (Centripetal Acceleration)**, reorganized into our 5-section format →
   `material_work/_reference/openstax_6.2/{reference.md,.json,.txt,side_by_side_fan.md}`.
   Independent of our pipeline = a real gold reference.
4. **Material eval** `tools/run_material_eval.py` (`.venv-eval`): raw BERTScore F1 (comparable
   to P-MAGIC), candidate material vs OpenStax reference. **Whole-passage F1 = 0.840 ± 0.002**
   (n=5); per-section top = "how the variables relate" **0.855** (the formulas the textbook
   shares); diversity 0.18 (low by design — material is consistent, so we DON'T feature it).
   Report → `material_work/_eval/material_eval_report.{md,json}`.
5. **vinsa_export rebuilt MATERIAL-centric** (`tools/prepare_vinsa_export.py` rewritten):
   per object `material/{material.json,.md,.txt}` + figures + PDFs + annotated video;
   top-level `_reference/openstax_6.2/` + `material_eval_report.md` + `_combined/materials.txt`
   + material-focused README (3 open Qs: reference choice, granularity, raw-vs-rescaled).
   Old question-export saved to `vinsa_export_questions_backup_*`.
6. **Advisor deck reframed** question → learning material (backed up to
   `presentation/_backup_*`): headline 0.856→**0.840 (material relevance)**, Method 2 =
   grounded learning-material generation (seed→prose diagram), eval = material vs authentic
   OpenStax, pipeline subagent C label = learning material, summary/status updated. Compiles.
   **Companions also updated**: narration.md, qa-prediction.md, presentation-notes.md,
   glossary.md, extended-explanations.md (all question/0.856/synthetic-ref/diversity → material/0.840/OpenStax).
   > Deck still says "Subagent C" for the LLM author (it's actually D now); cosmetic.
7. **Qwen quirk**: it's a reasoning model — with thinking ON it needs a big budget
   (`max_tokens≈24000`) or `content` returns empty (all budget spent in `reasoning_content`);
   `chat_template_kwargs.enable_thinking` toggles it. User wants thinking ON.

## 3e. Done THIS session (refresh 6) — LOOSE ENDS + MATERIAL PDF + EVAL POLISH
Followed up on the refresh-5 loose ends, then layout/eval requests from the user.

1. **Deck "Subagent C→D"** (loose end): slides + glossary now code-faithful **A (video) / B
   (figures) / D (learning material)**, with a note that C (questions) is omitted in the
   material-focused talk. (User chose "code-faithful A/B/D".)
2. **Angular-acceleration block** (loose end): **verified already resolved** — all 5 exported
   PDFs carry it (turntables *decelerating*, bike *uniform α≈0*, fan *accelerating*). No action needed.
3. **Fan absolute scale FIXED** (loose end + user gave the measurement): provisional 1.3 m
   gave an absurd orbit radius **1.84 m**. Real single blade ≈ **47–50 cm long × 15 cm wide**;
   `diameter_px` is the rotation-averaged **(W+H)/2** of the blade bbox ≈ **(L+w)/2 ≈ 0.32 m**.
   Set `physical_size = 0.32` in `templates/base-template-fan-doll/sidecar.json` + the fan
   workspace → orbit radius **0.45 m**, mean a_c **21.8 m/s²** (was 88), max 43.3. Relative
   kinematics (α, ω, T, CV) were already correct (scale-free).
   - **Re-run path used**: patched `pipeline_inputs.json` + sidecar → re-ran `run.py` + `figures.py`
     deterministically (ALL plots incl. `annotated_image.png` are deterministic from
     stats/kinematics) → cleared `material.json`/`questions.json`/`report/` → **re-enqueued**
     (tracking cache HIT, no re-track) so Subagents D+C regenerated prose with correct numbers,
     then render. Verified: material r=0.44, questions a_c=21.78, PDF shows r=0.454 m.
4. **Material PDF interleave** (`workspace_lib/analysis/render/report.py`): figures + the
   measurements table are now embedded **inline within the 5 material sections** (Scenario→
   annotated frame, variables→table, "what the video shows"→ω(t)/a_c(t), "reading figures"→
   summary/trajectory/r(t)/v(t)) — textbook-style, NOT a figure dump. Standalone "Key
   Measurements"/"Visual Analysis" sections dropped when material is present (fallback kept if
   no material). New: `FIG_META`, `SECTION_ARTIFACTS`, `_inline_figure/_inline_table/_section_artifacts`;
   `_material_block(material, stats)`. **All 5 reports re-rendered** (fan via re-enqueue; other
   4 by syncing seed `analysis/` into the workspace copy + `report.py` + latex-skill compile).
5. **Eval P/R + Table-3 metrics** (`tools/run_material_eval.py`): now reports BERTScore **P and
   R** (not just F1) + a triple block + LSTM caveat. **New numbers** (n=5): whole-passage
   **P 0.837 / R 0.842 / F1 0.840 ± 0.002**, per-section F1 top "how variables relate" 0.855,
   **diversity 0.204** (was 0.183 — fan material changed). **LSTM NOT reproducible** (needs
   P-MAGIC's own trained model — stated, not faked). Re-ran on `material_work/_eval/material_*.json`
   (pass the 5 files explicitly; glob also matches `material_eval_report.json`).
6. **Deck** (`presentation/centri-end-to-end.tex`, 36 pp / 28 frames): added a **P-MAGIC
   Table-3-style results slide** (frame 22/28: P/R/F1 M±SD + diversity + per-section diagnostic +
   LSTM/0.882 cross-ref notes); removed duplicate `0.840` blue cards on **1/28** and **20/28**;
   fixed clipping on **3/28** (`\resizebox` the pipeline diagram), **17/28**, **20/28** (tighter
   spacing + single-line cards + shorter caveat). **Companions updated**: narration (renumbered
   for new frame 22), glossary (A/B/D, diversity 0.204, LSTM entry), presentation-notes (new
   "## 22" + fan 21.8 m/s²), qa-prediction (new fan-scale + LSTM Q), extended-explanations (P/R + LSTM).
7. **Export rebuilt** (`tools/prepare_vinsa_export.py a2627aa2 cc9f02ce afe0f99f 711fffe8 8110ab0d`):
   new fan material/PDF + new `material_eval_report.{md,json}` (P/R, diversity 0.204); `_combined/materials.txt` refreshed.
   > **Deployment note**: the worker runs each job's OWN copy of `analysis/` (synced from
   > `workspace_lib` at job creation). New jobs inherit the interleave automatically; finished
   > workspaces only got it where I synced. Nothing committed (commit on request only).

## 3f. Done THIS session (refresh 7) — DECK REWORK FROM VINSA'S FEEDBACK
All work on `presentation/centri-end-to-end.tex` (now **42 pages**, footer counts **/33** main;
appendix + blanks excluded from the count). Compiles `pdflatex` ×2, no errors. Added
`\usepackage[most]{tcolorbox}` to preamble. **Nothing committed.** Drove edits off a WhatsApp
chat from Vinsa (pasted by user) + three follow-up asks.
1. **New side-by-side slide** "What is compared: our material vs. the reference (fan)" — two
   color-boxed columns: generated (Subagent D, grounded) vs OpenStax §6.2 gold, shown
   per-section (Scenario + How-variables-relate). Answers Vinsa's "I can't find the material
   output + the reference." **Used CURRENT fan numbers (r=0.44, a_c=21.8)** — the file
   `material_work/_reference/openstax_6.2/side_by_side_fan.md` is **STALE** (r=1.78/a_c=88.49,
   pre-refresh-6 scale); current fan material = `material_work/_eval/material_a2627aa2.json`.
2. **ALL P-MAGIC mentions removed** (user: don't name it). 11 occurrences → "the prior method"
   / "a prior multimodal method". Results-slide subtitle now "These numbers are ours; the metric
   is the prior method's"; table header "Our material, scored with the prior method's metric".
   Cross-ref "0.882 question-vs-prompt" kept but anonymized. **Companion .md files NOT scrubbed**
   (still say P-MAGIC + old numbering) — open item.
3. **Deck reordered** (Vinsa: "present from slide 20; defer earlier to backup"): leads with old
   page 20 **"From each case to grounded learning material"** → Method 2 Generation → Method 3
   Evaluation (incl. new side-by-side + results) → Paper 2 → System & status → Summary. Then
   **`\appendix` "Backup — how the system works"** divider, after which the deferred slides
   (contribution/headline, Method 1 Measurement, Validation cases = old pages 2–19). `\appendix`
   drops them from the page-count fraction = effectively hidden, one keypress away.
   Implemented via a Python block-move (head 1–53, block_b 401–827 to front, block_a 54–400 to
   appendix). **System & status stayed in MAIN** (it wasn't in the first 20) — Vinsa hinted it's
   "open-if-asked" backup; **offered to move it, not yet done**.
4. **Three blank BLACK blackout slides before Summary** (user: "empty divider… black screen,
   hide it"): `{\setbeamercolor{background canvas}{bg=black}\begin{frame}[plain]{}\end{frame}}` ×3.
5. **New "Next plan — evaluation metrics to try" slide** (after Status & roadmap) — Vinsa sent a
   metrics table photo; reproduced faithfully: BLEU (lexical), ROUGE-1/2/L (recall), **BERTScore ✓
   (used now, highlighted)**, BLEURT (learned quality), each with "what it measures". Framed as
   widening the battery beyond BERTScore.
6. **Reference-disclosure added** (deck): on the side-by-side slide + the score-computation
   slide — reference is authentic OpenStax §6.2 **reorganised** (not raw PDF, not paraphrased)
   into our 5 sections so candidate/reference align section-by-section, **built independently**
   of our generation (textbook "over time" = its own car/centrifuge examples, not our numbers),
   and **whole-passage F1 reported too** → not leaked, not selective. Pre-empts "is the reference
   rigged?". (Reference = ~506 words, source `openstax_6.2/reference.json`.)
7. **All 5 companion .md docs updated** (`presentation/`): **P-MAGIC fully scrubbed** → "the
   prior method" (matches deck; 0 mentions remain). narration.md + presentation-notes.md
   **reordered/renumbered** to the new running order (main 1–16 + BACKUP B1–B15) with narration/
   notes for the new side-by-side, next-plan-metrics and blackout slides + the reference
   disclosure. qa-prediction (new "is the reference rigged?" + metrics-roadmap Qs),
   extended-explanations (§5.3 rewritten "why it isn't rigged" + BLEU/ROUGE/BLEURT),
   glossary (prior-method entry, LSTM entry, added BLEU/ROUGE/BLEURT).
## 3g. Done THIS session (refresh 7 cont.) — HONESTY OVERHAUL + FINAL REORDER
Deck now **44 pages** (`pdflatex` ×2, no errors; footer counts **/34** main, appendix+blanks
excluded). **Nothing committed.** Triggered by user asking "what else do we need to be honest
about?" → I audited claims against the SOURCE and found 3 overclaims (see ledger below), then
reframed deck + all companions to mark planned-vs-done.
1. **Honesty reframes** (deck + companions): eval-methodology slide split **Run now (relevance)**
   vs **Planned — quality, NOT yet run** (LLM-judge + 10-teacher panel); auto prompt-sweep =
   **manual now / automation roadmap**; bilingual Bahasa = **planned**. "5 objects" → **"5 runs /
   3 phenomena (turntable×3, bike, fan)"** everywhere. Reference slides note **OpenStax §6.2 is
   uniform-motion-only → more references to be added**.
2. **NEW "Limitations & scope" slide** (honesty slide): scope today + planned fixes + "solid
   regardless" (angular results exact/scale-free; physics deterministic given trajectory).
3. **Pipeline slide:** flags the verification gate will be **extended to material prose** (planned).
4. **Final reorder** (user, by slide-fraction): main order is now **1–4 generation → 5–8 evaluation
   → §"Status & roadmap" {9 Status, 10 Limitations, 11 Next-plan-metrics, 12 Paper 2} → §"System
   internals & deployment" {13 at-a-glance, 14 lifecycle, 15 deployment, 16 agentic pipeline} →
   3 blackout slides → 17 Summary**; then `\appendix` backup (contribution, Method 1, validation
   cases). The 4 system/infra slides were moved to AFTER Paper 2 (resolves the old "move System &
   status to backup" open item). Done via Python block-moves.
5. **Layout fixes** (user-reported clipping): removed the 0.840 blue card then **both** remaining
   cards on methodology (5/34); trimmed score-comp (6/34); shrank pipeline diagram (`\resizebox
   0.74`, `below=9mm`) so the red "Planned" note fits.
6. **narration.md AND presentation-notes.md reordered** to match (9–17 reshuffled, §"Status &
   roadmap" + §"System internals & deployment" headers added, prose preserved). Both
   slide-anchored companions now in sync with the deck. Other companions are order-agnostic.

## 3h. PLANNED / NOT-YET-RUN ledger (the honesty audit — verified against source)
What the deck/companions now present as **planned**, NOT done (all confirmed absent in
`agent-backend/` source unless noted):
- **Quality evaluation NOT run** — LLM-as-judge + 10-teacher panel are *designed only*; no
  judge/teacher tooling in `tools/`. **Today we have RELEVANCE only (BERTScore 0.840).** Biggest
  honesty item.
- **Measurement-validity pilot = n=1 reported** (IMG_3075, 0.3%). **2 more sensor-paired clips
  captured** at `/home/damar/new-case/` (IMG_3071/3072 + .csv accel+gyro) → n=3 available but
  **NOT yet processed**. Offered to run the full 3-clip validation.
- **Prompt micro-sweep = MANUAL**, not in pipeline (the `/tmp/fan_sweep` finding); automation is
  roadmap. No `sweep/auto-probe` in `workspace_lib|worker|prompts`.
- **Bilingual EN/Bahasa = NOT built** (roadmap phase 3); no bahasa/translate in source.
- **Verification gate checks figures/numbers only**; extending to **material-prose correctness**
  (right physics, no wrong relations) is planned — until then prose rests on the (unrun) panel.
- **Reference covers UNIFORM motion only** (OpenStax §6.2); add references for non-uniform content.
- **Centre-override hardening** listed as a planned pipeline improvement (fan needed it most).
- **Scope honesty**: "5 runs / 3 phenomena" (turntable filmed 3×), not 5 independent objects.

## 3i. DEFERRED DISCUSSION (promised to user, not yet resolved)
- **#6/#7 framing**: how to present **F1 0.840 ± 0.002** (the tight SD = pipeline *consistency*,
  NOT quality) and **diversity 0.204** (low by design; suggested a *grounded-sections-only*
  diversity cut to prove output isn't templated). Not yet applied — talking points only.
- **#12**: tighten deck wording to "**reproducible for a given capture**" (physics deterministic
  given the CACHED trajectory; tracker non-deterministic, LLM prose varies). Not yet applied.

## 3j. Done THIS session (refresh 8) — PROF NOTE TRIAGE + TRACKING MODES + NEW FAN VIDEO
Drove off `presentation/note-from-prof.md` (prof's PPT feedback) + a new recapture video.
1. **Prof note triaged** → A = deck/scenario edits (value-first scene, 5W+1H + story,
   authentic personal context "Irfan rode bike to Taipei", relationships-via-annotation);
   B = **multimodal BERTScore** (LLM captions our figure vs reference figure → BERTScore the
   captions; answers prof's "input vs output bertscore?" = bring the image INPUT into a text
   metric); C = recapture/scale-up (data, his "red paper, slow, 10-15s" → the new video);
   D = **knowledge graph** → added to `PAPER2_LEARNING_STUDY.md` §4+§7 (defer, ask Vinsa). **DONE: D.**
2. **NEW VIDEO `/home/damar/centri/IMG_3750.MOV`** (75 s, 60 fps, 1920×1080 rot −90 →
   portrait; **5-blade ceiling fan with an ORANGE/RED PAPER band on one blade**, prof's
   recapture). Two hand intrusions (t≈3, t≈12). Findings:
   - **Slow portions** (e.g. 55–59 s, ~5 rpm): SAM3 `"fan blade"` object-track = **100% clean**
     single-blade orbit (verified overlay — it even locks the orange blade). Best for slow.
   - **Peak 10–20 s** (~32 rpm): SAM3 **aliases** (5 identical blades → wagon-wheel, ω≈0) AND
     colour fails (marker motion-blurred into a smear; static orange clutter at frame bottom).
     **Higher fps doesn't fix exposure blur.** → **frequency mode**: ring-FFT gives blade-pass
     **2.70 Hz** (all 12 probes ±0.03 Hz) → **ω=3.39 rad/s, T=1.85 s, ~32 rpm**, a_c=ω²r.
3. **NEW FEATURE — tracking modes (user ask): `object | color | frequency`, sidecar flag +
   agent fallback.** All write the same `api_cache.json`; **frozen core untouched**.
   - `workspace_lib/analysis/color_track.py` — HSV marker track (sat-scored + temporal gate +
     ROI + red wraparound). On this clip: marker orbit is **perfect but sparse** (CV 0.003,
     centre = hub, but ~38% coverage — marker visibility-limited). Shines for a big/always-visible marker.
   - `workspace_lib/analysis/freq_track.py` — blade-pass FFT → ω + **synthesized clean orbit**
     (bbox encodes orbit radius so generic ref-sizing recovers diameter_px; physical_size =
     orbit radius in m). Writes `frequency_meta.json`; flags `kinematics_from_frequency_synth`.
   - **Orchestrator** `prompts/orchestrator.txt` Step 1.2b (parse `tracking_mode`/`tracking_config`)
     + Step 2.1 branch (color/frequency run `python -m analysis.{color,freq}_track`, subprocess).
   - **Docs**: `data-contract.md §1a` (full mode table + sidecar examples), `pipeline-internals.md`,
     `object-detection-prompts.md` (when wording isn't enough → switch mode).
   - **VALIDATED end-to-end**: fed a frequency-synth cache through the REAL frozen `analysis.run`
     → mean_omega −3.387, mean_r_m 0.30, **mean_ac 3.442** (=ω²r), period 1.855, motion uniform. ✓
   > Scratch artifacts in session scratchpad: `input_video.mp4` (30fps full), `input_video_full60.mp4`
   > (planned), `clip_10_20_60.mp4`, `testclip.mp4`, `freq_cache_10_20.json`, `color_*.json`, overlays.
   > **Provisional scale**: peak orbit physical radius assumed 0.30 m (rescale when measured; one number).
4. **PENDING**: actually RUN IMG_3750 through a job (peak→frequency mode, or slow→object); then **A**
   (deck edits) and **B** (multimodal BERTScore tooling). Nothing committed.

## 3k. Done THIS session (refresh 9) — DOWNLOADS, PDF RECOVERY, WINDOWED FREQ, + BLUR CORRECTION
Continued refresh 8. **Nothing committed.** Scratchpad (session): `input_video_full60.mp4` (full
75s/60fps portrait), `clip_10_20_60.mp4`, `freq_cache_full.json`+`freq_meta_full.json` (windowed),
`freq_fan_student.pdf`/`freq_fan_teacher.pdf`, `peak_marker_zoom.jpg`.

1. **⚠ BLUR CLAIM WAS WRONG (correct refresh-8 §3j + docs).** Tested directly:
   - At peak the fan turns only **~0.54 rev/s** (2.7 Hz blade-pass ÷5) = **~6.5°/frame at 30 fps** —
     below the 36° identical-blade aliasing threshold, so "speed aliasing" never cleanly explained it.
   - **SAM3 `"fan blade"` @ 60 fps on the 10–20 s peak window = 100 % cov, 6.60 rev/10 s, ω≈4.15 rad/s
     — CLEAN.** Higher fps **DOES** fix it.
   - The marker is **SHARP at peak** (orange blob 120×124 px, area 9653 @ t=17 s) — NOT smeared.
   - ⇒ The 10–20 s tracking failure was **30 fps wagon-wheel under-sampling, NOT motion blur**.
     **Simplest path for the new fan = object (SAM3) mode at 60 fps** — frequency mode still valid/useful
     but not required; colour likely also works at peak (sharp marker; earlier fail was strict HSV +
     static bottom clutter, not blur). **TODO: fix `docs/object-detection-prompts.md` + `data-contract.md §1a`
     which currently overstate "blur defeats colour / fps doesn't help".**
2. **Windowed (time-resolved) frequency mode added** — `freq_track.analyze_windowed()` +
   `synth_trajectory_varomega()` + CLI `--window-s/--hop-s`; orchestrator freq branch passes
   `tracking_config.window_s/hop_s`. Full-clip **ω(t)**: spins **up 0.63→peak 3.77 rad/s @ t≈16–19 s**,
   coasts **down to 0.63 by t≈52 s** (147 windows, probe spread ~0). Through the frozen pipeline:
   a_c max **4.27**, but the clip is **two-phase (accel+decel)** → single-regime classifier mislabels
   `motion_type=accelerating` (one-α approx); the faithful record is `frequency_meta.omega_t`. (FFT res
   = 1/window → ω quantised to 0.628 rad/s steps at 2 s windows.)
3. **New-video job run** (peak 10–20 s, frequency mode, job `4b8ce653`): ran end-to-end (material +
   questions + stats: **a_c 3.44**, ω 3.39, T 1.85, r 0.30), **failed only on the known runaway guard**
   at the report step. **PDF recovered deterministically**: `docker compose exec worker … python -m
   analysis.render.report` in the workspace (path = container `WORKSPACE_DIR=/home/damar/centri/
   agent-backend/workspaces`), then `pdflatex ×2` → `student_edition.pdf` (8 pp) + `teacher_key.pdf`.
   Material is correctly grounded (mentions 3.4 m/s², 1.85 s, 0.30 m, CW). Scene label cosmetically
   "fan rotor on fan rotor" (tracked==ref).
4. **Multilingual reference set** → `agent-backend/material_work/_reference/multilingual/` (+README
   manifest). **23 PDFs**: ja/zh/ko/id/ms (#59,60,61,63,64,66,68,70,71,72,73,77) + en/es/fr/de
   (#36,44,45,46,49,50,51,52,54,55,56). Failed-from-network (#58 daido HTML, #65 jssnd .edu.cn, #67
   yonsei) + HTML/flipbook (#37–41,48,53,62,69,74–76,78) + #42/43 OpenStax-ES (no-LLM notice, skipped)
   are all listed in the README. Expands beyond OpenStax §6.2 per prof's "add references" note.
5. **Deck A (prof note) — PARTIAL**: `presentation/centri-end-to-end.tex` Scenario bullet rewritten →
   value-first, **5W+1H** story, **authentic daily-life context** ("Irfan rode his bike across town"),
   relationships **shown through annotation** (image/graph/table), student-centred. **NOT compiled yet;
   more deck edits + a `pdflatex ×2` pending.**
6. **User wants the new scene at FULL duration** (not the 10 s window). Full-duration windowed cache is
   built (`freq_cache_full.json`); **full job NOT re-submitted.** Given finding #1, consider running it
   **object mode @ 60 fps** (clean, single trajectory) vs frequency-windowed (handles two-phase but
   quantised + mislabels motion_type).

## 3l. Done THIS session (refresh 10) — DOC FIX, DECK COMPILE, TASK B BUILT, FULL FAN TRACK RUNNING
Picked up the refresh-9 to-do. **Nothing committed.** Scratchpad (this session
`ae29af72-…`): `sidecar_3750_object.json`, `job_id_3750_full.txt`, `vlmtest/` (probe + extracted
ref figs), `mm_args.txt`, deck compile logs.
1. **#6 blur overstatement FIXED** (`docs/object-detection-prompts.md` + `data-contract.md §1a`):
   the 10–20 s tracking failure was **30 fps under-sampling (wagon-wheel), NOT motion blur** —
   60 fps DOES fix it (marker stays sharp). Both docs now say **try `object` @ 60 fps first**;
   frequency mode reframed to "under-samples even at 60 fps, or you need ω(t)", not "blur".
2. **Deck recompiled** (`presentation/centri-end-to-end.tex`, `pdflatex ×2`, **44 pp, clean**):
   the refresh-9 uncompiled scenario edits (value-first / 5W+1H / "Irfan rode his bike") are now
   in the PDF. (Further scenario/annotation slides for task A still optional.)
3. **TASK B BUILT + RUN — multimodal BERTScore** `tools/run_multimodal_eval.py`: a vision LLM
   (local multimodal **Qwen3.6-35B**, `input:[text,image]`, thinking OFF) captions each figure →
   BERTScore the captions vs reference-figure captions. Brings the **image INPUT into the text
   metric** (prof's "input vs output BERTScore" ask). Reference figures = **OpenStax §6.2's own 2
   figures** extracted from `Chapter6_Section2.pdf` → persisted at
   `material_work/_reference/openstax_6.2/figures/{fig1_velocity_geometry,fig2_examples_car_centrifuge}.jpg`.
   Captions cached by file hash in `material_work/_eval/caption_cache.json`. **Result (n=5,
   turntable×3/bike/fan a2627aa2): multimodal relevance F1 = 0.829 ± 0.004** (P 0.832/R 0.827) —
   sits beside the prose **0.840**. Per-figure: annotated_image/summary_panel match the car/centrifuge
   a_c–v–r figure strongest (~0.85); time-series plots ~0.82. **Captions verified faithful** (fan
   annotated_image read r=0.454 m; ac_t read mean~20/peak~45; matches known numbers, no hallucination).
   Out: `material_work/_eval/multimodal_eval_report.{md,json}`.
   > Caveat (same as prose eval): same-domain physics captions share vocab → BERTScore floor is
   > high and the spread is narrow; this is a relevance/agreement measure, not quality.
4. **#1 FULL fan track RUNNING** — user chose **object @ 60 fps, full 75 s**. Submitted
   `input_video_full60.mp4` (1080×1920, 60 fps, 4526 frames) with object-mode sidecar
   (`visual_cues:["fan blade"]`, center `[0.398,0.479]`, **physical_size=0.32 PROVISIONAL** —
   rescale when blade measured; relative kinematics ω/T/α are scale-free). **Job
   `8d95a817-2eac-4ef4-b84b-4a9618036cb9`**, in the **track** phase (~11 min in; ETA ~1.5–2.5 h
   for 4526 frames). When done: expect the runaway guard at report step → **recover PDF
   deterministically** as in §3k.3 (`docker compose exec worker … python -m analysis.render.report`
   in the workspace, then `pdflatex ×2`). Two-phase clip → single-regime classifier will likely
   mislabel `motion_type` (faithful ω(t) record lives in the cache / would need windowing).
   > Submit gotcha: API rejects `application/octet-stream` → curl needs `-F "video=@f;type=video/mp4"`.

## 3m. Done THIS session (refresh 10 cont.) — ENGLISH REFERENCE SET + MULTI-REF EVAL + DECK
1. **English reference set downloaded** → `material_work/_reference/english/` — **18 verified PDFs**
   (MIT OCW CC BY-NC-SA, arXiv 1602.06361, university lecture notes UIUC/OSU/USNA/EMU/Alabama/
   ColoradoMesa/Sydney/Hawaii/Oklahoma, worksheets Flipping Physics×2/BU/APlusPhysics/USC/UBC/PMT).
   All confirmed real centripetal content (26–167 kw hits). `README.md` carries type/pages/license.
   **2 failed** (recoverable): #17 Philadelphia `.edu.jo` unreachable, #27 Conant 403. **Skipped on
   purpose**: OpenStax editions with the explicit "no-LLM ingestion" notice (we have §6.2 already);
   HTML-only sources (LibreTexts/Lumen/Pressbooks/Khan — no clean PDF). DL gotcha: needs a browser UA;
   verify `%PDF` magic (some return HTML/403). The lone English in `multilingual/` is #36 Bronx Sci.
2. **Multi-reference robustness eval** `tools/run_multi_reference_eval.py`: each candidate whole-passage
   vs each reference; raw PDFs reduced to their most centripetal-dense ~320-word window (keyword-anchored);
   reorganized §6.2 = gold anchor. **Result (n=5 × 19 refs): gold §6.2 F1 0.840 ± 0.002 (reproduces
   the official number exactly); set-wide mean 0.808 ± 0.003; best-match = §6.2 for every run.**
   Per-ref top: USC lab 0.824 / Hawaii 0.823 / OSU 0.819; bottom UBC/EMU/USNA ~0.78. Out:
   `material_work/_eval/multi_reference_eval_report.{md,json}`. The official metric STILL = vs reorganized
   §6.2; the 19-set is a **robustness band**, NOT the headline (raw, not 5-section-reorganized).
3. **Deck updated** (`centri-end-to-end.tex`, still 45 pp, `pdflatex ×2` clean, **verified no clipping**):
   robustness band **0.808 ± 0.003 / 19 refs** added to the results slide; the 3 "more references to be
   added" caveats (methodology, score-comp, limitations slides) rewritten to "robustness checked vs 19
   English refs" (honest: gold still §6.2, raw set still mostly uniform-motion). Companions updated:
   narration §8, presentation-notes §8, qa-prediction "is the reference rigged?" answer all cite the band.

## 3n. Done THIS session (refresh 10 cont.) — REORG GOLD + TWO-RESULTS EVAL + NEW FAN JOB DONE (kinematics UNRELIABLE)
1. **Reference reorganization** `tools/build_reference.py` (Qwen text, thinking off, grounded on PDF):
   reorganized the **8 prose English refs** into our 5-section format →
   `material_work/_reference/english_reorganized/*.json` (mit, arxiv, emu, alabama, pmt, usna,
   flipping_intro, flipping_deriv). Verified faithful (usna keeps Mungan's jerk/snap detail).
   Classification (per content signals): PROSE(8)+openstax = gold; SLIDES(13/14/20/21);
   WORKSHEET(19/25/26/29); LAB(22/28). zsh `${=VAR}` needed for word-split in loops.
2. **Two-results eval** `tools/run_reference_comparison_eval.py` → `material_work/_eval/reference_comparison_report.{md,json}`:
   - **A. Reorganized prose gold**: OpenStax-only **0.840 ± 0.002** (official, reproduced);
     whole prose-gold set (9 refs) **0.827 ± 0.008**. Per-section: "how variables relate" 0.852 top,
     grounded "over time" 0.808 bottom.
   - **B. Reorganized vs RAW (same prose sources)**: **0.827 ± 0.008 vs 0.801 ± 0.012 (Δ +0.026)** —
     every ref improves with reorganization (+0.007…+0.040). Reorg aligns format, removes whole-PDF noise.
   - **C. Separate buckets (raw)**: slides 0.815, lab 0.820, worksheet 0.801 — reported distinctly
     (question/figure relevance, not material).
3. **⚠ NEW FAN JOB `8d95a817` DONE** (object@60fps, full 75 s, 4526 frames, ~50 min) — completed
   THROUGH report (PDFs rendered, no runaway guard). BUT **kinematics UNRELIABLE**:
   - Geometry CLEAN: **100% coverage, rock-solid radius r=0.32 m (std 0.0013)**, center drift 0.36 px.
   - ω CORRUPTED by **5-identical-blade hopping**: ω(t) shape is right (spins up to PEAK @ t≈15 s,
     coasts down by t≈68 s = two-phase), but magnitude inflated ~4× (object peak ω≈16 rad/s vs
     frequency-mode measured peak ~3.4–3.8). Gap grows with speed = hopping signature (radius stays
     perfect since all 5 blades same radius; θ jumps 72°). `std_omega 3.41` on mean 6.84.
   - **motion_type MISLABELED "decelerating"** (α=-0.18, R²=0.996) — single-regime quadratic θ-fit on
     genuinely two-phase motion.
   - **Material/PDF carry the inflated numbers** (mean_ω 6.84, a_c 18.73, "decelerating") → NOT
     physically trustworthy as-is. **Do not ship this PDF.**
   - TRUE kinematics = FREQUENCY mode (blade-pass, hop-immune): peak ω ~3.4–3.8 rad/s, two-phase ω(t)
     in `freq_cache_full.json` (cached refresh 9). This case DEMONSTRATES why freq mode + honest flags exist.

## 3o. Done THIS session (refresh 10 cont.) — ROI BUG FOUND, ω RECONCILED, FREQ RE-RUN
**The object job `8d95a817` was BROKEN by a bad auto-ROI** (user caught it: "the roi crop is insane"):
1. **ROI collapsed to a 232×232 box on the HUB** (`roi_crop x_off=314 y_off=804 232×232`), excluding
   the whole blade span. SAM3 "fan blade" locked a small **hub** feature, not the orange blade-tip marker.
   → tracked a **60px orbit** mis-scaled as 0.32 m; the intended orange marker (blade tip, ~357px) was
   NEVER tracked. **Object job radius/a_c are meaningless. Do not ship its material/PDF.**
2. **Diagnostics built** (scratchpad `ae29af72`): per-frame Δθ shows NO blade-hopping (all steps smooth
   <16°, none near ±72°) — `hop_diag.png`; annotated video `fan_annot_peak.mp4`; ROI-vs-true-orbit overlay
   `orbit_compare.png` (60px hub circle vs 357px marker orbit).
3. **ω RECONCILED via rigid-body check**: ω is shared hub↔tip. Color marker (real blade tip) gives peak
   ω≈3.25; object hub feature over-counts by a constant **~3.5×** (it was reading blade-passes). **TRUE
   peak ω≈3.5 rad/s — matches frequency mode** (refresh-9 freq was right; object full-clip was the anomaly).
4. **Color mode re-run** (`tools`→`analysis.color_track`, **20 s** local CPU vs 50 min SAM3): tracks the
   marker correctly at **357px orbit** (radius 337–385, rock-solid) but **coverage blur-limited** — 82% at
   slow start, ~15% in fast middle (marker desaturates when spinning). Loosening HSV→100% but catches
   clutter (radius 13–364). Good params: `--hsv-lo 168,90,90 --hsv-hi 12,255,255 --roi-center 429,919
   --roi-radius 430 --min-area 150 --max-step 260`. Cache `color_full.json`.
5. **USER CHOSE: frequency mode for the full two-phase**, scaled by color's 357px orbit.
   - Ran `analysis.freq_track --hub 429,919 --ring-radius 200 --n-blades 5 --orbit-radius 357 --window-s 2.5
     --hop-s 0.5 --fmax 8` (4.5 s) → **146 windows, ω 1.0→3.52 rad/s, two-phase (peak @ t≈15 s)**.
     Caches `freq_cache357.json` + `freq_meta357.json`. Validation `omega_validation.png` (freq + marker +
     object÷3.5 all agree).
   - **Submitted real-pipeline FREQUENCY job `1c183872-4350-4c41-8cfb-d07de3f674d3`** (sidecar
     `sidecar_3750_freq.json`: tracking_mode frequency, n_blades 5, ring_radius 200, orbit_radius_px 357,
     window_s 2.5, hop_s 0.5, center_frac [0.3972,0.4786], **physical_size 0.6 m PROVISIONAL** — rescale
     when blade-tip orbit measured; relative ω/T scale-free & correct). Expect runaway guard at report →
     recover PDF as in §3k.3. motion_type will mislabel two-phase (single-regime) — faithful ω(t) in
     `frequency_meta.json`.

## 3p. Done THIS session (refresh 10 cont.) — FREQ JOB VERIFIED + NEW FOCUSED DECK
1. **Freq job `1c183872` VERIFIED**: PDFs rendered (student/teacher, no runaway guard this time).
   Geometry now CORRECT (full fan, r=0.600 m circle spans blades, marker visible). Numbers correct
   (mean ω 1.75, mean a_c 2.29, max a_c 7.44, T 4.17 s; provisional 0.6 m scale). **Caveat**: material
   Scenario prose says "accelerates at a steady rate" — the single-regime mislabel (misses coast-down);
   numbers right, motion narrative single-phase. PDF copied to scratch `new_fan_student.pdf`.
2. **NEW FOCUSED DECK `presentation/centri-cases-eval.tex`** (11 pp, `pdflatex ×2` clean, verified no
   clipping). Reuses main-deck preamble + `\usepackage{colortbl}` (needed for `\rowcolor`). Structure:
   what-it-covers → §Cases {4-cases-at-a-glance table (bike uniform / turntable decel / fan-toy accel /
   NEW fan two-phase, highlighted row); new-fan ROI-bug slide (`newfan_orbit_compare` 60px hub vs 357px
   marker); new-fan 3-method validation (`newfan_omega_validation`)} → §Evaluation {material relevance
   (gold 0.840 / reorg set 0.827 / two-results reorg-vs-raw +0.026); references classified (prose gold +
   slide/lab/worksheet buckets); multimodal 0.829 (figure→caption→BERTScore)} → Summary. Figures copied
   to `figs/newfan_{orbit_compare,omega_validation,geometry}.png`.

## 3q. Done THIS session (refresh 10 cont.) — REFERENCE TABLES + PER-REF M±SD
- Extended `tools/run_reference_comparison_eval.py` to output **per-reference mean ± SD** (reorg + raw)
  and **per-bucket-reference mean ± SD**; re-ran (report B/C tables + JSON `per_ref`/`bucket_per_ref`).
- New deck `centri-cases-eval.tex` (**now 12 pp**): replaced the one "references classified" summary slide
  with TWO table slides per user ask ("mention references directly as table; show mean+SD; examples"):
  (1) **Prose gold (9 sources)** — Source / Type / F1 M±SD table (OpenStax 0.840 … Flipping-deriv 0.814,
  set 0.827±0.008) + two example-excerpt tcolorboxes (OpenStax + MIT "how variables relate");
  (2) **Diagnostic buckets (10 sources)** — Source / Bucket / F1 M±SD + bucket-means table.
  Compiles clean, layout verified.

## 3r. Done THIS session (refresh 10 cont.) — DECK POLISH (cases-eval)
`presentation/centri-cases-eval.tex` now **11 pp** (footers 1/8→8/8), compiles clean:
- **Merged** the Material-relevance + prose-gold slides into ONE "Material relevance --- the reference
  set and the score" (9-source table M±SD = left, two-results + per-section + example = right) — killed
  the duplicated 0.827. Buckets stay separate.
- **Added "Why BERTScore?" note**: it's the prior method's metric (comparability); BLEU/ROUGE/BLEURT =
  planned wider battery.
- **Slide 3 (ROI bug)**: image height-sized + centered (no right clip); "The recapture" moved into the
  right text column.
- **Multimodal slide**: KEPT the figure→caption→BERTScore tikz diagram AND added real VLM caption
  examples (our fan annotated_image caption vs OpenStax car/centrifuge caption); REMOVED the
  "input vs output BERTScore" line (user).
- **Title**: Vinsa Kharisma credited as "evaluation collaborator" (NOT co-advisor — she's a labmate/peer;
  user declined the full co-author byline + declined mirroring on the main deck for now).

## 3s. Done THIS session (refresh 11) — DIFFICULTY-TIERED MATERIAL + GROUNDING VERIFIER
Driven by `note-29` (user's note): one video → **3 learning materials at 3 difficulty tiers**
(basic / intermediate / advanced), then eval each tier. **Nothing committed.** Scratchpad
(`333c37a0-…`): `test_tiers.py`, `seed_fixed.json`, `tier_{basic,intermediate,advanced}.json`,
`tier_eval_report.md`, `raw_intermediate.txt`.
1. **Reviewed user's tiering spec** (Bloom's Revised + Cognitive Load Theory). Verdict: theory
   grounding is right, but the user's spec is **task/question-shaped** (Bloom action verbs) =
   belongs to **Module C (questions)**. For **material** (exposition) the genre is different →
   wrote a **material-tier spec**: `agent-backend/docs/difficulty-tiered-material-spec.md`. Tiers
   keyed to actual seed fields (basic=r+inward-pull, no equations; intermediate=ω/v/a_c/T/f +
   relations; advanced=α+timeline+a_c∝ω²+scale caveat); Bloom=objective the passage equips, CLT=
   primary lever. One LLM call per tier (A3B bleeds tiers if combined). Output keeps `sections`
   dict → existing `run_material_eval.py` works unchanged → `material.{tier}.json`.
2. **VALIDATED live** on Qwen3.6-35B (`192.168.1.205:8083`, thinking ON, max_tokens 24000): 3
   clean JSON tiers, ~7–11 s each, no empty-content, tiers correctly differentiated + self-labeled
   Bloom/CLT. Test harness `scratchpad/test_tiers.py`.
3. **Manual review caught 2 bugs (BERTScore-invisible) → FIXED:**
   (a) **Motion-type faithfulness:** basic+intermediate first called the *spinning-up* fan
   "steady" → added spec constraint #4 (qualitative speed-change at ALL tiers; only α value +
   timeline reserved for advanced) + rounding #5.
   (b) **Formula identities didn't compute** ("6.59×1.78=12.2"; claimed a_c=ω²r=88.5 when ω²r=77.3).
   Root cause: `material_seed.py:71` reported r=`mean_r_m` but v & a_c are built from
   `calibration.r_fit_m` (`kinematics.py:200`) — differ ~3.8% (1.844 vs 1.777 px-scale; 0.4539 vs
   0.4374 m now); PLUS for non-uniform motion **mean(a_c)=mean(ω²)·r > (mean ω)²·r (Jensen)**.
   **FIX (`material_seed.py`):** report r=`r_fit_m` (v=ωr closes exactly per instant), keep
   `measured_radius_m` as cross-check, add `consistency_note` (verify identities at a TIMELINE
   INSTANT, not the means). Spec/harness constraint **5b**. **Re-validated: all 3 tiers close
   arithmetic** (intermediate verifies at t=3.02 s; advanced explains Jensen explicitly).
4. **Eval-reference confound MEASURED** (3 tiers vs OpenStax §6.2): basic **0.815**, int **0.838**,
   adv **0.841** = **REVERSE of note-29's "basic-high/advanced-low" hypothesis**. §6.2 is
   equation-dense, so more-advanced (more vocab-overlapping) material scores higher ⇒ a single
   fixed reference measures **lexical density, not quality**. To test the hypothesis honestly →
   tier-matched references (Module C `classify` mode can sort the 19-ref set); else reframe as
   motivating a real quality metric.
5. **GRADING DISCUSSION (user: "is BERT good for this?")** — BERTScore is relevance-only and BLIND
   to the arithmetic bug. Plan = multi-axis exploiting our **ground truth (the seed)** which the
   prior method lacked. **BUILT** `tools/grade_material_grounding.py` — deterministic, model-free,
   4 checks: (1) arithmetic closure, (2) number-grounding to seed, (3) tier compliance,
   (4) motion faithfulness. Validated (passes good, fails bad with correct arithmetic, no false
   positives after hardening vs unit-slashes/value-lists/constant-α). **Found REAL errors in 2 of
   6 SHIPPED materials**: turntable `_recover_afe0f99f` ((4.861)²×0.148=3.50 not 3.992; 2π/4.861=
   1.29 not 1.37) and bicycle `8110ab0d` (0.385²/0.075=1.98 not 2.09 — **this PDF is in
   vinsa_export!**). Same mean-vs-instant bug class; BERTScore passed all of them.
   > Files changed (uncommitted): `workspace_lib/analysis/material_seed.py` (r_fit + consistency_note),
   > NEW `docs/difficulty-tiered-material-spec.md`, NEW `tools/grade_material_grounding.py`.
   > NOT wired into live pipeline yet (orchestrator 3× loop, render 3 PDFs, per-tier eval, verifier
   > as a hard gate). Old shipped materials need regen with fixed seed to verify clean.
6. **Memory:** `centri-tiered-material.md` created (spec, validation, the bug+fix, the confound,
   the verifier + shipped-material finding).

## 3t. Done THIS session (refresh 12) — TIERED FIGURES + STYLED PDFs + TIER REGEN
User asked to (a) render the 3 tiers as actual PDFs, (b) stop reusing the SAME figures for
every tier, (c) style the PDFs. **Nothing committed.** All work re-rendered in the fan
workspace `job_a2627aa2` (manual, NOT yet wired into live pipeline). Outputs in
`agent-backend/material_work/_tiers_fan/`: `material.{basic,intermediate,advanced}.json`,
`v3_{tier}_{student,teacher}.pdf`, `thumb_{tier}-1.png`.
1. **Figure tiering (the pivot — figures must match prose load, CLT).** Reusing the full
   7-fig + table set at every tier broke the basic tier (a "one idea" passage next to a
   quadratic a_c(t) graph + 13-row table). Now each tier embeds a difficulty-matched set:
   - **`figures.py`**: new `fig_annotated_image_basic` (clean frame: orbit circle + radius
     arrow, NO pixel axes/vectors) + `fig_trajectory_basic` (single-colour path, no phase
     legend) → `annotated_image_basic.png`, `trajectory_basic.png`; refactored frame load to
     `_first_frame()`. main() emits 9 plots + summary + **2 basic variants**.
   - **`report.py`**: `TIER_ARTIFACTS` (per-tier section→figure/table map),
     `_measurements_table(level=core|full)` (core = r/ω/v/a_c/T/f only; full adds peak/α/calib),
     `_material_block` reads `material["tier"]`. **basic=2 figs/no table, int=3 figs/core table,
     adv=5 figs/full table.** Untiered material.json still renders the default set (back-compat).
   - **spec** `docs/difficulty-tiered-material-spec.md`: new **§1a figure tiers** table +
     **HARD CONSTRAINT #10** ("Reading the figures narrates ONLY the tier's allowlist").
2. **NEW tool `tools/generate_tier_material.py`** — proper per-tier generator (one Qwen call
   per tier, thinking ON, max_tokens 24000, JSON out). Feeds each tier's **figure allowlist**
   INTO the prompt so prose↔figures stay in sync (closes the desync where basic prose narrated
   absent graphs). Regenerated all 3 tiers from the FIXED seed `seed_fixed.json` (r_fit 0.4539 +
   Jensen consistency_note; the workspace's own seed is the pre-refresh-11 r=mean version).
   **Verified**: basic narrates only the 2 pictures, int names table+1 graph, adv the full set.
3. **Styling (`report.py` `_preamble`/new `_titleblock`/`_header_block`)**: per-tier accent
   (basic **green** / int **blue** / adv **purple**; default teal), a **LEVEL badge** in the
   masthead, accent sans-serif `titlesec` headings w/ trailing rule, `microtype`, tinted table
   header row, 1-line gray metadata strip (was 4 bold lines), looser leading/arraystretch.
   Also fixed an **inaccurate caption** (annotated_image.png claimed velocity/a_c *vectors* the
   frame never drew → now "fitted orbit + radius").
   > **GOTCHAS (all resolved):** worker TeX has **no `lmodern`** (dropped it; CM default is fine;
   > `tlmgr install lmodern` if wanted). f-string `}}` collapses to one `}` → broke `\colorbox`
   > (use concatenation). **Stale `.pyc` (worker has 3.12 AND 3.14 caches)** served the OLD
   > renderer once → **`rm -rf analysis/render/__pycache__` before any in-workspace render**, and
   > `rm $ed.pdf` before lualatex so a FAILED compile can't leave a stale PDF to copy. Container
   > mounts ONLY `workspaces/` → pipe edited files in via `cat host | docker compose exec -T
   > worker sh -c "cat > $W/..."`. Teacher edition needs **lualatex** (✓ U+2713 in answers;
   > pdflatex dies). **Qwen `192.168.1.205:8083` is reachable from the worker container, NOT the
   > host sandbox** — run generation/curl inside `docker compose exec worker`.
4. **DEFERRED (agreed order, user picked "both"):** figures done now → **next = independent
   difficulty signal** (Flesch-Kincaid readability + element-interactivity COUNT per tier,
   reported beside BERTScore) to turn the asserted ladder into measured evidence (critique #1).
   Critique list (what else is weak): single-axis difficulty; artifact shaped to be scorable not
   to teach; figure tiering invisible to every current metric; no cross-tier number consistency;
   advanced collapses on uniform clips; polishing provisional kinematics. See chat for full list.

### NEXT SESSION TO-DO (ordered) — current as of refresh 12 end
**State (refresh 12):** 3 tiers now render as STYLED, figure-tiered PDFs (basic/int/adv =
2/3/5 figures, color-coded + level badge), prose regenerated from the fixed seed with the
figure-allowlist constraint. NOTHING COMMITTED; still manual on `job_a2627aa2`.
- **RETEST F1 (next)** — the tier prose was REGENERATED (refresh-11 numbers 0.815/0.838/0.841
  are now stale). Re-run `tools/run_material_eval.py --materials material.basic.json
  material.intermediate.json material.advanced.json` (in `.venv-eval`) on the new
  `material_work/_tiers_fan/material.{tier}.json` vs OpenStax §6.2; record the new per-tier F1
  (P/R) M±SD and whether the advanced≥int>basic ordering (the eval-reference confound) holds.
  > Run the eval where it can reach files; the prose is plain JSON (no GPU needed). Watch the
  > glob caveat (pass the 3 files explicitly; glob also matches `*_report.json`).
- **THEN the difficulty signal** (readability + element-interactivity count) — see §3t.4.
- **Wire 3-tier into live pipeline** (orchestrator loops Subagent D ×3 → `material.{tier}.json`;
  render 3 PDFs; per-tier eval grouping; grounding verifier as a pre-ship GATE) — still pending.
- Regen the 2 buggy SHIPPED materials (`_recover_afe0f99f`, bicycle `8110ab0d`) + refresh `vinsa_export`.

### NEXT SESSION TO-DO (ordered) — current as of refresh 11 end
**State (refresh 11):** 3-tier material generation + deterministic grounding verifier VALIDATED
offline; seed bug (r_fit/Jensen) fixed at source. Eval-reference confound measured. **Discussing
better eval methods next.** NOTHING COMMITTED.
- **Eval method discussion (ACTIVE)** — BERTScore insufficient; decide the grading battery
  (grounding verifier ✓ built; LLM-judge rubric; teacher panel; tier-matched refs). User wants to
  talk through options.
- **Regen the 2 buggy shipped materials** (`_recover_afe0f99f`, bicycle `8110ab0d`) with the fixed
  seed + instant-verification rule, re-verify clean, refresh `vinsa_export`. (bicycle PDF currently
  shipped with a wrong number.)
- **Wire 3-tier into live pipeline** (orchestrator loops Subagent D ×3 → `material.{tier}.json`;
  render 3 PDFs; per-tier eval grouping; grounding verifier as a pre-ship GATE).
- **Tier-matched references** to test note-29 honestly (Module C `classify` to bucket the 19-ref set).

### NEXT SESSION TO-DO (ordered) — current as of refresh 10 end
**State:** new fan job `1c183872` DONE + verified (the frequency re-run; `8d95a817` object run is the
BROKEN one — do not use). New focused deck `presentation/centri-cases-eval.tex` = **11 pp, clean**.
Eval rework done (reorg gold 0.827 / two-results / multimodal 0.829 / per-ref M±SD). **NOTHING COMMITTED.**

- **BLEU/ROUGE — DECISION PENDING** (user paused here): deck note is just "BLEU / ROUGE planned". To
  actually run: `pip install sacrebleu rouge-score` into `.venv-eval`, extend `run_reference_comparison_eval.py`
  to compute BLEU+ROUGE candidate-vs-reorganized-gold, add to deck. **Expect LOW numbers** (lexical n-gram
  overlap on PARAPHRASED prose: BLEU ~0.05–0.15, ROUGE-L ~0.2–0.35) — that's expected and *motivates*
  BERTScore; must be framed that way or the low numbers look bad. ~15 min.
- **New fan scale is PROVISIONAL 0.6 m** (orbit radius) — rescale when the real blade-tip orbit is measured;
  relative kinematics (ω peak 3.5, T, two-phase) are correct/scale-free. Patch sidecar + re-render deterministically.
- **Two-phase classifier mislabel** — new fan material Scenario says "accelerates steadily" (single-regime);
  numbers right, narrative misses the coast-down. Extending classifier to two-phase = roadmap.
- **Optional deck consolidation**: fold the new-fan two-phase case + the reference tables / multimodal into the
  MAIN deck `centri-end-to-end.tex` (user hasn't decided main-vs-two-decks). Vinsa credit NOT mirrored to main
  (user declined for now); on cases-eval she's "evaluation collaborator" (NOT co-advisor).
- **#4 multilingual eval = PARKED** (decided: English-only official metric; multilingual 23 PDFs = roadmap/Paper 2).
- **Commit when asked** — large uncommitted working tree (deck, tools, docs, references, eval reports).

## 4. Module C (core code change) — DONE/verified
3 tiers: easy=recall/read (no formula, 2dp), intermediate=apply (formula in `solution`),
advanced=analyse/compare. Each q tagged `format` (text/image/graph/table). `questions.json`
is now a dict `{object_name, scenario, questions:[{stem,question,difficulty,format,answer,
unit,solution,hints,given}]}` (`stem`=app, `question`=LaTeX report, identical text).
Files: `.pi/agents/circular-motion.subagent-c-questions.md` (+2 legacy copies synced),
`workspace_lib/analysis/render/report.py`, `prompts/orchestrator.txt`, docs.
> `.pi/` was root-owned; we `chown -R damar:damar .pi/agents .pi/agent/agents`.

## 3c. Done THIS session (refresh 4) — FAN KINEMATICS RESOLVED
1. **Root-caused the "noise-dominated" fan**: it was NOT noise. Two causes:
   (a) **wrong rotation center** — the user-marked center sat **158 px off** the true
   orbit axis, so r/θ/ω were computed about the wrong point → fake radius_unstable
   (CV 0.39), center_mismatch, high_center_drift. The pipeline already had a great
   RANSAC fit (1.6% residual) but its policy was "always trust the human mark".
   (b) the residual ω variation is **real physics**: the fan is **spinning up at
   constant α=1.18 rad/s²** (θ(t) quadratic R²=0.99989, ω 3.2→10.2 rad/s).
2. **Fix (geometry.py)**: adopt the RANSAC fit over a user mark only when it's
   unambiguously better — tight inlier residual AND much lower radius CV
   (self-guarding vs the degenerate giant-circle case). Adds flag
   `center_overridden_from_mark`, `center_source="ransac_override"`. Fan radius CV
   **0.39→0.10**, center drift→0.
3. **Full spin-up support** (kinematics.py/writer.py/render/report.py): robust
   motion-model classifier via quadratic θ-fit (replaces the flicker-prone
   ω-derivative thresholding that mislabeled the spin-up STABLE); new stats block
   `angular_acceleration` {motion_type, alpha_rad_s2, alpha_r2, omega_initial,
   omega_final, a_t_mean_m_s2}; `period_mismatch`/`unstable_phase_linearity` now
   gated on motion_type (only fire for uniform motion); report table shows α / a_t.
4. **Regression-checked all 10 workspaces**: only the fan triggers the override;
   **turntables correctly reclassify as decelerating** (α≈−4, hand-spun coast-down);
   bike stays uniform. No regressions.
5. **Re-ran fan job `a2627aa2`** (cache HIT, no re-track, 205 s): flags now ONLY
   `center_overridden_from_mark`; questions regenerated and **now use α** (advanced
   q cites "angular acceleration during the increase phase is 1.18 rad/s²").
   **Re-exported** all 5 objects; `_combined` rebuilt; **auto_eval re-run (n=59):
   BERTScore F1 0.856, diversity 0.603**.
   > NOTE: edited `workspace_lib/analysis/*`; on re-enqueue the worker does NOT
   > re-seed, so I synced the 4 files into the workspace's `analysis/` copy (root-
   > owned → did it inside the worker container). Turntable/bike NOT re-run, so their
   > exported stats still lack the new block (re-run them if you want α there too).

## 5. Tracker findings — RESOLVED for the fan (kinematics RESOLVED — see §3c)
**BIG correction (refresh 3): production tracker is SAM3-CPP (GGML)**, served by
`/home/damar/sams2/sam3cpp/api_master_sam3.py` at `10.0.0.1:8086` (supervisor `run_sam3.sh`,
conda env `sam3`, recycles via `POST /reset`). It shells out to a **C++ binary + GGML models**
(`sam3-q4_0.ggml`, `sam2.1_hiera_large_f16.ggml`) — **NOT** the YOLO-World `worker_segmenter.py`
python path (that's stale; the docs describing YOLO-World grounding are out of date).
- **Prompt sweep proof**: YOLO-World gives `"fan blade"`=0/12 but production SAM3-CPP gives
  `"fan blade"`=100% → confirms YOLO-World is NOT production. Faithful sweep = live `/track`.
- **Fan winner (production /track, 72-frame clip)**: `"yellow toy"`/`"hanging toy"` = **100%**
  (both track the orbiting doll, confirmed by overlay); single words `"toy"/"doll"/"ball"/
  "ornament"/"small toy"/"white toy"` = **0**; `"fan blade"` = 100% but centroid ~hub → no orbit.
  **Best prompt is TRACKER-SPECIFIC** (LA liked single `"toy"`; SAM3-CPP needs 2 words).
- **Sweep scripts**: `/tmp/fan_sweep/{track_sweep.py (live /track), viz.py, sweep.py (YOLO-World)}`,
  run via `/home/damar/miniconda3/envs/sam2/bin/python`. YOLO-World weights `/home/damar/sams2/yolov8l-worldv2.pt`.
- **⚠ FAN KINEMATICS OPEN (investigate later)**: doll tracks 100% but orbit radius is tiny
  (~55 px, near hub) → angular noise dominates. 5 s vs 7 s windows gave 10×-inconsistent ω
  (0.58 vs 5.9 rad/s) and period/ω disagree within a run. Likely needs: larger-radius object,
  reshoot (closer/slower), or a smoothing/▒robust-ω fix for small-radius orbits. The exported
  fan (`a2627aa2`) carries honest flags; questions/material are valid for BERTScore regardless.

### 5-old. LocateAnything (LA) — secondary path (still valid)
**Key finding (still true)**: prompt wording is the dominant tracking lever. Both SAM3-CPP
and LA are text-conditioned open-vocab detectors.
- LA `/track` (+`/reset`) **built** into `test/locateanything_worker.py` (per-frame
  tracking-by-detection; returns SAM3's exact schema: `{status,trajectories:{label:
  [{frame,cx,cy,bbox}|miss(cx:None)]},video_info}`). Run via conda env **`locateanything`**
  (`/home/damar/miniconda3/envs/locateanything/bin/python test/locateanything_worker.py`,
  torch 2.12.1+cu130, port **8087**, RTX 5090).
- Fan results (10s clip, 605 frames): blade **100%**; doll **6%** (`"cream colored doll"`)
  → **`"toy"` 100%** detection (20-frame sweep). Full ranking + montages in `test/`
  (`fan_la_*_montage.jpg`, `fan-tracking-findings.md`, `la_track_fan_10s.json`).
- **Caveat still open**: `"toy"` 100% *detection* but **box size unstable** (sometimes the
  whole fan → centroid≈hub, sometimes tight on doll). The full `"toy"` `/track` **timed out
  (>700 s)** — LA `/track` is **slow (~10 min+ for 605 frames × 2 targets vs SAM3 ~66 s)**,
  a real con for adopting LA. **Next step (cheap):** run `"toy"` via `/segment` on ~60
  sampled frames, **size-filter** boxes (drop whole-fan, keep doll-sized), and **circle-fit**
  the centroids around the hub (`rotation_center_frac=[0.532,0.560]` → ~(575,1075) px) to
  decide if fan kinematics is recoverable or needs a reshoot. (Hub px, CV<0.25 ⇒ clean.)
- **Networking blocker** (must fix before repointing pipeline to LA): worker container can
  **not** reach LA. Gateway is `172.19.0.1` but `172.19.0.1:8087` is unreachable from the
  container, while SAM3 `10.0.0.1:8086` works — likely a host firewall on the docker bridge.
- **Decisions made**: user chose **switch pipeline to LA** (blocked on networking) and for
  the fan **track `"toy"`** (pending the circle-fit validation).

## 6. Runtime state (as of refresh 3)
- **Workspaces on disk (current jobs)**: turntable `cc9f02ce afe0f99f 711fffe8`,
  **bicycle `8110ab0d`**, **fan 5 s `15948414`** (export removed, ws may remain), **fan 7 s
  `a2627aa2`** (current). Old originals `5fb0e7dd 7c1b742d 9d6db89b` may persist.
- **vinsa_export/**: as of refresh 5 it is **MATERIAL-centric, 5 objects** (turntable×3, bicycle
  `8110ab0d`, fan `a2627aa2`): per object `material/` + figures + PDFs (Learning Material) + video;
  top-level `_reference/openstax_6.2/`, `material_eval_report.{md,json}` (F1 0.840), `_combined/materials.txt`.
  Old question-based export → `vinsa_export_questions_backup_*`.
- **Fan sidecar**: `templates/base-template-fan-doll/sidecar.json` = `visual_cues:["yellow toy"]`,
  ref `"fan blade"` size 1.3 m (provisional), `rotation_center_frac:[0.579,0.503]`. Portrait-baked
  clips: `IMG_3678_{10s,5s,3to10}_portrait.mp4` (rotation `-90` baked in; pipeline reads 1080×1920).
- `.venv-eval/` = CPU torch + bert_score + sentence-transformers for `run_auto_eval.py`.
- SAM3-CPP tracker `10.0.0.1:8086` (production, can be slow ~10 min/300–420 frames, recycles);
  Qwen inference `192.168.1.205:8083`. LA worker (`:8087`) currently DOWN.

## 7. Tooling & how-to
- `tools/prepare_vinsa_export.py <job_ids>` → `vinsa_export/<obj>/` (bucketed candidate
  txts, questions.json, figures, **annotated_video.mp4**, PDFs) + `_combined/` + README.
- `tools/run_auto_eval.py <job_ids>` (use `.venv-eval/bin/python`) → BERTScore relevance +
  STS diversity + synthesized reference base in `vinsa_export/<obj>/references/`.
- **Submit a job**: `POST 10.0.0.1:8088/analyze` `-F video=@f -F "sidecar=$(cat sc.json)"`,
  header `X-API-Key: $(grep ^API_KEY= agent-backend/.env|cut -d= -f2)`.
- **Re-enqueue an existing workspace** (no re-upload): `docker compose exec -T -w /app worker
  python -c "from worker.tasks import run_pi_analysis; run_pi_analysis.delay('<job_id>')"`.

## 8. Operational gotchas
- **Detection prompt wording dominates tracking reliability** — simple nouns (`"toy"`), not
  phrases (`"cream colored doll"`). See `docs/object-detection-prompts.md`. Sidecar
  `visual_cues`/`label` should be simple nouns.
- **`celery revoke --terminate` stalls the prefork pool**; the follow-up restart **drops
  prefetched/acked tasks** AND a deleted-workspace zombie causes a `/root/.pi` symlink error.
  Cleaner kill = `docker compose restart worker` then delete the job; re-enqueue from the
  existing workspace if it survived.
- **`cleanup_expired_workspaces` (beat, hourly) and job deletion remove workspaces** — that's
  how bicycle/fan were lost. Export/eval promptly after a job completes.
- zsh: `status` is read-only — don't use as a var. API binds `10.0.0.1:8088` (not localhost).
- Calibration: `px_per_m = reference.diameter_px / physical_size_m`.

## 9. What's next (prioritized)
**A. Deck/scenario edits (prof note)** — value-first scene description; 5W+1H + a short story
   on the scenario (slide 2/34, student-centered); authentic personal context (e.g. "Irfan
   rode his bicycle to Taipei", daily-life); show how-variables-relate THROUGH annotation on
   the table/image/video, not only prose. File: `presentation/centri-end-to-end.tex` (+ companions).
**B. Multimodal BERTScore (prof note, his main methodology ask)** — LLM-caption each figure
   (ours vs the OpenStax reference figure) → BERTScore the captions, bringing the image INPUT
   into the text metric (his "input vs output bertscore?"). Buildable with `.venv-eval` + a
   vision model; new tool under `agent-backend/tools/`. Most novel; do after the video run.
**Run IMG_3750** through a job (peak 10–20 s → `tracking_mode:"frequency"`, or a slow window →
   object). Pre-cache then submit (worker-stop / inject api_cache.json, see §7). Provisional
   orbit radius 0.30 m → rescale when measured.
0. ✅ **Module D / learning material DONE this session (refresh 5, see §3d)**: generation
   wired into the real pipeline, all 5 objects requeued + exported, OpenStax reference,
   material eval **BERTScore F1 0.840 ± 0.002**, deck + companions reframed to material.
   Remaining: send Vinsa `vinsa_export/` + the 3 open Qs (reference choice, granularity,
   raw-vs-rescaled); get her reference/convention → recompute for official numbers. Optional:
   add OpenStax §6.1 (rotation/angular velocity) to the reference for T/f/α coverage;
   promote afe0f99f to a clean real-pipeline run.
   > ✅ refresh 6: deck "Subagent C"→"D" DONE; material PDF interleaved; eval now reports
   > P/R + diversity (0.204); P-MAGIC Table-3 results slide added; export rebuilt.
1. ✅ **Fan kinematics + absolute scale RESOLVED** (see §3c + §3e): off-axis center + real
   constant-α spin-up fixed; **absolute scale fixed refresh 6** — measured blade → `physical_size
   = 0.32`, orbit radius 0.45 m, mean a_c 21.8 m/s² (was the absurd 1.84 m / 88 from the
   provisional 1.3 m). All 5 exports carry the `angular_acceleration` block.
2. **Send Vinsa package**: `zip -r vinsa_export.zip vinsa_export/` and send with the 3 open
   questions (reference flavor, diversity convention = mean_sim vs 1−mean_sim, aggregation).
3. Get Vinsa's references + scripts → swap in for official comparable numbers (ours are PRELIM).
4. **Polish/deliver the advisor deck** (`presentation/centri-end-to-end.tex`) — rehearse,
   add any figures the prof wants (he focuses on numbers/method/pedagogy/stats).
5. LLM-as-judge (parked); human-eval rater app; statistics (κ, Pearson, ANOVA-family).
6. **Decide LA vs SAM3-CPP for production**: SAM3-CPP works with the right (2-word) prompt but
   can be slow; LA accurate but ~10 min/600 frames + docker-bridge networking still unfixed.
7. Follow-up from the prompt lesson: make `/suggest-scene` + AnnotateScreen emit simple nouns,
   and consider an auto prompt-micro-sweep on the live tracker before committing a sidecar.

## 10. File map
- Research: `PAPER_GAP_ASSESSMENT.md`, `PAPER2_LEARNING_STUDY.md`, `SESSION_CHECKPOINT.md`,
  `chat-log.txt`, `document-3.pdf`.
- **Advisor deck**: `presentation/centri-end-to-end.tex` (+ `.pdf`) — Beamer/metropolis,
  `pdflatex centri-end-to-end.tex` ×2. Numbers/methods/pedagogy/stats focus.
- **Fan tracker sweep**: `/tmp/fan_sweep/{track_sweep.py,viz.py,sweep.py}` (live-/track + YOLO-World).
  Production SAM3-CPP source: `/home/damar/sams2/sam3cpp/api_master_sam3.py` + `run_sam3.sh`.
- Module C: `agent-backend/.pi/agents/circular-motion.subagent-c-questions.md` (+2 copies).
- **Module D (learning material)**: seed `workspace_lib/analysis/material_seed.py` (+ called
  in `analysis/run.py`); subagent `.pi/agents/material-gen-subagent.md`; render section in
  `analysis/render/report.py` (`_material_block`); orchestrator wave in `prompts/orchestrator.txt`.
  Tools: `tools/{build_material_seed,generate_material,run_material_eval}.py`.
  Reference: `agent-backend/material_work/_reference/openstax_6.2/`; eval out:
  `agent-backend/material_work/_eval/material_eval_report.{md,json}`; quick-path materials in
  `material_work/<obj>/`. Export rewritten: `tools/prepare_vinsa_export.py` (material-centric).
- Pipeline seed: `agent-backend/workspace_lib/analysis/` (`render/report.py`, `geometry.py`).
- LA tracker: `test/locateanything_worker.py`; model `locateanything-3b/`; conda env
  `locateanything`. **Production SAM3-CPP source: `/home/damar/sams2/sam3cpp/api_master_sam3.py`
  + `run_sam3.sh` (C++ binary + GGML), env `sam3`.** (`sam3/worker_segmenter.py` = stale YOLO-World alt.)
- Tooling: `agent-backend/tools/{prepare_vinsa_export,run_auto_eval}.py`; `.venv-eval`.
- Tracking evidence: `test/fan-tracking-findings.md`, `test/fan_la_*_montage.jpg`,
  `test/la_track_fan_*.json`.
- Docs: `agent-backend/docs/object-detection-prompts.md` (+ data-contract, pipeline-internals,
  subagents, agents-behaviour updated).
- Deliverable: `agent-backend/vinsa_export/`.
