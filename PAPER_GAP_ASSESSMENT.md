# Centri vs. P-MAGIC — Gap Assessment & Next-To-Do

Living doc. Compares the current Centri implementation (video-based measurement +
Flutter app + Socratic tutor) against the P-MAGIC paper (Hwang, Sari, Purba, Azhar,
*J. Educational Computing Research*, 2026 — `document-3.pdf`). Maintained alongside the
direction from Prof. Hwang and labmate/team-lead Vinsa (`chat-log.txt`).

Legend: ✅ parity/better · ◑ partial/divergent · ❌ missing

---

## Where we stand vs. the paper

| Area | Paper (P-MAGIC) | Centri | Status |
|---|---|---|---|
| Object recognition | GPT-4o Vision | Local VLM (Qwen3) + SAM3 tracking, coverage gate/retry, HITL annotate | ◑ divergent (local model, by lab requirement) |
| Kinematics source | **Phone IMU** (accel+gyro, Phyphox) | **Video CV tracking** → RANSAC circle fit | ◑ fundamental divergence |
| Multimodal output | text + image + graph + table + annotations | same **+ annotated video + native in-app charts** | ✅ superset |
| Phase annotation | increase / steady / decrease (threshold) | `stats["phases"]`; single-push clips = one stable phase (intended) | ✅ (bicycle clip would exercise all 3) |
| Difficulty model | **3 levels** easy/intermediate/advanced (Bloom-mapped) | **reworked to 3 levels** (was Bloom-6), installed + verified end-to-end | ✅ aligned |
| Evaluation | auto (BERT/STS/LSTM) + human (teachers, rubric) + stats | telemetry feedback only | ❌ biggest gap |
| Ground-truth validation | leans on IMU | limited sensor-vs-video spot checks | ◑ see note |
| Curriculum alignment | Indonesian MoE Grade-11 | implicit | ◑ adopt her framing |
| Tutor (Socratic 4-stage) | — (her v2 work) | implemented (ported) | ✅ keep, parked |

---

## Done (2026-06-21)

**Module C reworked to match Vinsa's / the paper's method.**
- Replaced the Bloom's-6-level question bank with the paper's **3 difficulty tiers**
  (easy = remember/understand, intermediate = apply, advanced = analyse/compare),
  each tagged with a content `format` (text/image/graph/table) so the multimodal
  ablation set (text-image / text-graph / text-table) has material.
- New `questions.json` is the dict shape the API/app already expect
  (`{object_name, scenario, questions:[{stem, difficulty, format, answer, solution,…}]}`)
  — this also **fixed a live schema mismatch**: the old bare-array + `question`/`bloom_level`
  output was being rejected by `app/result_data.load_worksheet` (expects a dict).
- Each question carries both `stem` (app) and `question` (LaTeX report) with identical
  text, so both consumers work without editing seeded report code further.
- Files changed (by me): `workspace_lib/analysis/render/report.py` (group by tier, read
  new keys, backward-compatible), `prompts/orchestrator.txt` (report §8 + manifest:
  `bloom_distribution.json` → `difficulty_distribution.json`).
- Installed into all three def copies and **verified end-to-end** (job `cc9f02ce`): 12
  questions, `{easy:6, intermediate:4, advanced:2}`, all 4 formats; `/result` worksheet
  populates; student+teacher PDFs render with tier subsections.
- **Eval tooling built**: `tools/prepare_vinsa_export.py` (export package) and
  `tools/run_auto_eval.py` (preliminary BERTScore relevance + STS diversity, in
  `.venv-eval`). Preliminary turntable numbers: BERT F1 ≈ 0.856 (paper ≈ 0.882),
  diversity ≈ 0.62. See the session checkpoint for full detail.

**Ground-truth note (for the draft / reviewers).** Sensor-vs-video spot checks show the
**graph shape and peak timing agree**; absolute ω differs. Per Vinsa, phone IMU readings
themselves vary with sensor placement and manufacturer — so absolute agreement isn't the
right bar. Frame the claim as **relative/structural validity** (trend, peak, phase shape),
not absolute-value calibration against a single phone. (A turntable at a known fixed RPM
would give a true reference if absolute accuracy is ever challenged.)

---

## Next to-do

### 1. Evaluation harness (the big gap) — priority, weekend target
Vinsa's method (`chat-log.txt`): automatic eval = **BERTScore (F1/R/P)** (and BLEU) of
system output vs. a **hand-built reference** (not textbook — textbooks aren't authentic);
human eval = **SMA physics teachers** (she has contacts) on a rubric. Her question case
compares text-vs-text in a 2-column Excel/Colab; our case is **learning material →
compare PDF-vs-PDF**.
- [ ] Generate **5 outputs across ≥2 objects** (turntable + bicycle wheel/fan) for her to
      reference-build against. (She asked for this before Monday.)
- [ ] Reproduce her Colab BERTScore snippet against our generated questions/material so
      our numbers are directly comparable to her study.
- [ ] **Our preferred addition: LLM-as-judge.** We think BERT/BLEU are weak proxies for
      *question quality* (they measure surface/semantic overlap to a reference, not
      pedagogy). Plan: keep BERTScore for comparability with her paper, but add an
      LLM-as-judge rubric (relevance, answerability, difficulty-fit, concept accuracy,
      annotation correctness) as the primary quality signal. Justify in the draft.
- [ ] **Human-eval mini-app**: a simple rater UI for physics teachers to score generated
      learning materials/questions on a Likert rubric (mirror Table 2 of the paper so
      results are comparable). Output → CSV for stats.

### 2. Statistics (no strong opinion yet — parked, but needed for a paper)
- [ ] Inter-rater reliability (Cohen's κ) across teacher raters.
- [ ] Auto-vs-human agreement (Pearson) — the paper's RQ3.
- [ ] Per-level / per-modality comparisons (the paper used ANOVA → Kruskal-Wallis →
      Mann-Whitney; Welch/Brown-Forsythe + Games-Howell when variances unequal).
- Decide later whether we replicate her exact tests or simplify for the pilot.

### 3. Curriculum alignment
- [ ] Adopt the paper's Indonesian MoE Grade-11 framing for the difficulty levels in the
      draft and (optionally) in the Subagent C prompt rationale.

### 4. Research-draft notes
- [ ] State the **local-model** choice (Qwen3, lab requirement) and that detailed
      prompting compensates — contrast with the paper's GPT-4o.
- [ ] Frame video-tracking vs IMU as a contribution (no phone bolted to the object;
      measures the real object), with the relative-validity caveat above.

### 5. Parked / future
- Socratic tutor (already built) — hold for the v2 "influence on learning" study the
  professor described (perceptions + learning gains).
- Bicycle **two-rotation** recognition (pedal vs wheel) — professor's stretch goal.
- Reliability hardening of the video recognition (lighting/angle/sensor-quality
  sensitivity) before student deployment.

---

## Learning-material quality rework — notes/feedback backlog (2026-07-05)

Built on commit `b59cf79`. Addresses the defects Vinsa/Prof. Hwang flagged in the
generated material (title drift, prose↔table sign contradictions, "fan blade on fan
blade" naming, advanced ≈ intermediate, tracking-jargon leakage) plus the app-surfacing
gap. **Now LLM-live-validated (2026-07-05)** against the inference server — see the
live-results block below. `MATERIAL_REWORK_STATUS.md` holds the full per-file detail;
this table is the durable tracking home.

| WS | What | Status |
|---|---|---|
| WS-1a | Naming/seed hygiene: `dedup_display_name()`, unsigned ω/v (kills −2.12 vs 2.08 contradiction) | ✅ code + offline |
| WS-1b–1e | `material_tiers.py` rework: shared 5W+1H frame overwrites tier titles, `TIER_ANCHORS` distinct instants, RULE 8/8b vocab fences | ✅ code + offline |
| WS-2 | Gate unification → single `analysis/material_gate.py` (arithmetic, grounding, tier, motion, vocab, story-fence, cross-tier, frame); tests 9/9 | ✅ code + live |
| WS-3.1 | Seed `angle_milestones()` + `narrative_context` (from `sidecar.json scene_context`) | ✅ code + offline |
| WS-3.2/3.3 | Basic angle-at-time figure `fig_angle_points_basic()` (CVD-validated), wired into report | ✅ code + offline |
| WS-4 | tier → user-facing `difficulty_level` (report badge, orchestrator 8b, eval header) | ✅ code + offline |
| WS-5 | Surface material in app + **Defect B** (dead `student_edition.pdf` link → `student_edition*` glob + `tier_pdfs`); backend schema + Flutter `_MaterialSection`, `flutter analyze` clean | ✅ code + offline |
| WS-6 | Eval tooling: BLEU/ROUGE in `run_material_eval.py`, new `run_llm_judge.py`, `split_references_by_difficulty.py` | ✅ code (scores not yet run on new set) |
| WS-7 | Docs: `capture-protocol.md`; spec §9 resolved → tier-matched refs, new §10 (no-4th-tier) | ✅ code |
| WS-7.2 | Backlog table + live results (folds in `MATERIAL_REWORK_STATUS.md`) | ✅ done here |
| WS-8 | Best-of-N regen + external hints file (`material_hints.md`); 35B self-correction limitation | ✅ code + live |

**Offline-verified this rework:** gate tests 9/9 · fake-LLM e2e (titles equal, per-tier
instants distinct, gate JSON has `frame`+`cross_tier`, no "X on X") · figure render+eyeball
· report render (badge, angle fig, no dup titles) · API schema round-trip (+ old cached
results still validate) · PDF resolver (tiered/single/missing) · BLEU/ROUGE unit checks ·
reference classifier · `flutter analyze` clean.

### LIVE results — 5-seed sweep, 2026-07-05 (Qwen3.6-35B @ `192.168.1.205:8083`)
Regenerated all 5 eval seeds through the reworked generator:
- **EI monotonicity 5/5**, **titles equal 5/5**, **cross-tier PASS 4/5**, all tiers fully
  clean 3/5 (13/15 tiers). Gate JSON carries `frame`+`cross_tier` every run.
- Spot-confirmed the original defects are gone: no title drift, no "X on X", advanced ≠
  intermediate (distinct worked instants), grounded/consistent numbers.

**Post-sweep fixes (this session):** `_STEADY` false-positive fixed; ω² grounded as the
sanctioned `a_c=ω²·r` intermediate; idiom guards ("on track"/"work together"); quote-T/f
rule (no re-derivation); **best-of-N failure-informed regen** + separate cross-tier budget;
**external hints file** `workspace_lib/analysis/material_hints.md` (steers the first pass —
live-eliminated the stubborn `recorded`).

**Documented limitation — Qwen3.6-35B self-correction.** The 35B drafts well but corrects
poorly on regen (re-emits or trades banned words). Durable strategy = steer the first pass
via the hints file, not lean on regeneration. Full generalization needs a bigger model or a
review-and-select loop (cf. Utami SocioMathLLM CoT candidate selection). Residual gate flags
are proceed-but-flag stochastic single-word cases; the pipeline never hard-blocks.

### Still open (eval metrics + build steps)
- **Reference-based scores on the regenerated set** (gate verdicts done via the sweep; these
  are NOT yet run on the new material): `split_references_by_difficulty.py` → tier-matched
  `run_multi_reference_eval.py` (BERTScore), `run_material_eval.py` (BLEU/ROUGE),
  `run_llm_judge.py`. Target: F1 within noise of 0.840.
- **PDF compile** (texlive), **full Flutter build/run**, formal **A-B vs `job_477df73f`**.
