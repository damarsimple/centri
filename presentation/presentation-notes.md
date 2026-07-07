# Centri — presentation notes: where each slide invites questions

Slide-anchored prep. For each slide: the deeper background to have in your head, and the question that slide tends to invite, so you're never caught flat. Pairs with `qa-prediction.md` (full answers) and `glossary.md` (terms).

> **Order:** the talk opens on the pedagogy/evaluation story; measurement internals, validation cases and the contribution slide are in the **Backup** (after the Summary, under `\appendix`). The prior IMU method is named only as **"the prior method"** on stage. Three black slides before the Summary are a blackout buffer.

---

# MAIN TALK

## 1 — From each case to grounded learning material
**Background:** real generated material, the narration following the regime. Bike uniform (steady ω, period 1.18 s), turntable decelerating (a_c falls with ω), fan accelerating (ω 2→10, α 1.18). This is the *opening* slide now, so set the frame: "this is the output; I'll show how it's measured if you want it."
**Invites:** "Did the model compute these numbers?" No — the numbers are from the physics via the seed; the model wrote the prose around them.

## 2 — Grounded, multimodal generation
**Background:** one passage per scene in five sections (scenario, variables, relationships, over-time, figures); a deterministic seed supplies all numbers; multimodal figure references.
**Invites:** "How is it kept correct?" The seed gives the model the variables, formula relations and ω(t); the prompt forbids any number not in the seed.

## 3 — Four modalities (stimuli)
**Background:** the three images are real pipeline figures the material reads from; they enable the modality comparison.
**Invites:** "Are these auto-generated?" Yes, all seeded figure code; the table and graph come straight from the measured data.

## 4 — Pedagogy seam
**Background:** learning material (fixed) vs tutor (adaptive). The "two captures to one" point is the protocol-simplification argument.
**Invites:** "Is the adaptive tutor built?" The content side is; the ability/misconception modelling is the next phase being ported.

## 5 — Evaluation methodology
**Background:** split is now explicit — **run now**: automatic BERTScore *relevance* vs an authentic OpenStax reference (0.840). **Planned, not yet run**: the quality half — LLM-judge + 10-teacher panel (κ, ANOVA, Pearson). Similarity ≠ quality is the key caveat, and the reason the quality half exists.
**Invites:** "Have you run the teacher study?" Be honest: not yet — relevance is run, quality is designed. "Why trust BERTScore then?" We don't, for quality; it's only there for comparability. Quality will be the panel and the judge.

## 6 — How the score is computed
**Background:** greedy token matching for P/R/F1, whole-passage and per-section. The reference is OpenStax §6.2, *reorganized* into our five sections — not the raw PDF, not paraphrased — so the two align section-by-section. Set: 5 objects, F1 0.840 ± 0.002.
**Invites:** "Did you cherry-pick the reference to match?" No: reorganized (not rewritten) authentic textbook, built independently of our generation; whole-passage F1 is reported too.

## 7 — What is compared (side-by-side, fan)  *(new slide)*
**Background:** left = our grounded fan material (r 0.44 m, ω 6.59, a_c 21.8), right = OpenStax §6.2 reorganized into the same sections. The "how variables relate" rows nearly coincide (→ highest F1 0.855); scenario/figures diverge (→ our grounded value-add, lower F1 by design). This slide exists specifically to pre-empt the "is the reference rigged?" question.
**Invites:** "So you compare against a curated excerpt, not the raw textbook?" Yes, and say why it's fair: authentic text, reorganized not paraphrased, structurally aligned for a meaningful section-level score, done independently (the textbook's 'over time' section is its own car/centrifuge examples), and whole-passage F1 reported so it isn't selective.

## 8 — Automatic evaluation results
**Background:** mirrors the prior method's Table 3. Whole-passage BERT P 0.837 / R 0.842 / F1 0.840 (±0.002) + diversity 0.204; per-section F1 peaks on "how the variables relate" (0.855, shared formulas) and dips on the grounded sections (our value-add). LSTM fluency is omitted — it needs the prior method's own trained model. Their Table 3 overall F1 is 0.882 (question-vs-prompt, different reference; not head-to-head). **Robustness (new):** scored vs an independent **19-source** English reference set (universities/OER/worksheets) → set-wide mean **0.808 ± 0.003**; closest single source for every run is still the reorganised §6.2 (0.840). Tool: `tools/run_multi_reference_eval.py`; refs in `material_work/_reference/english/` (raw, keyword-windowed). Point: the number isn't an artifact of one reference.
**Invites:** "Why no LSTM score?" We won't fake a non-comparable proxy; we report the four metrics that reproduce exactly. "Diversity is only 0.204?" Low by design — one topic, one structure, so we lead with relevance, not diversity. "Is this self-comparison?" No — the reference is published textbook content our material never saw.

## 9 — Multimodal relevance (figure in the metric)  *(new slide)*
**Background:** answers the advisor's "input vs output BERTScore?" — a vision LLM captions each figure (image→text), then BERTScore vs the reference *figure*'s caption. Visual-channel F1 **0.829 ± 0.004** (P 0.832 / R 0.827), beside prose 0.840. Per-figure: annotated frame + summary panel match the OpenStax car/centrifuge figure strongest (~0.85); time-series plots ~0.82. Tool: `tools/run_multimodal_eval.py`; captioner = local multimodal Qwen (thinking off); reference figures from `Chapter6_Section2.pdf`.
**Caveats to say out loud:** relevance not quality; same-domain captions share vocab → high floor, narrow spread (same as prose). Captions verified faithful (read actual rendered values, e.g. r=0.454 m, no hallucination).
**Invites:** "Is the caption just echoing your numbers?" No — the reference caption is the textbook diagram's; the match is on the physics described, and whole-figure-set F1 is reported, not cherry-picked.

## SECTION — Status & roadmap
## 10 — Status and roadmap
**Background:** five runs / 3 phenomena done end to end, eval package delivered; limits are reference-size for absolute accel, and face-on assumption for the circle fit; roadmap ordered by risk.
**Invites:** "What's the biggest risk?" The accuracy pilot generalising beyond the first clips. That's why it's phase zero.

## 11 — Limitations & scope  *(new slide)*
**Background:** the honesty slide. Scope today: measurement validity = 1 sensor-paired clip reported (+2 captured, IMG_3071/3072, pilot in progress); generation = 5 runs / 3 phenomena (turntable ×3, bike, fan); quality eval (judge + teachers) designed but not run; OpenStax §6.2 is uniform-motion-only. Planned fixes: prose-level verification gate, hardened centre correction + automated prompt sweep, run the quality half + more references. Solid regardless: angular results exact + scale-free, physics deterministic given the trajectory.
**Invites:** "So what's actually proven?" Relevance + reproducible angular kinematics on the pilot set; quality and broad validity are the next experiments. Leading with this *builds* credibility — don't skip it.

## 12 — Next plan: evaluation metrics to try  *(new slide)*
**Background:** the co-author's metric table. BERTScore ✓ is the one reported now; BLEU (lexical n-gram precision), ROUGE-1/2/L (content recall), BLEURT (learned quality) are the next additions. Framed as widening the battery beyond a single embedding score.
**Invites:** "Why not these already?" Time/scope; BERTScore was the comparability anchor. "Won't BLEU/ROUGE be low for paraphrased material?" Expected — that's why they're complementary, not the headline; BLEURT and the teacher panel carry quality.

## 13 — Paper 2 (learning study)
**Background:** pre/post/retention, text-only vs multimodal, ANCOVA with pre-test covariate, effect sizes, cognitive load.
**Invites:** "How do you separate format from difficulty?" Both are tagged independently, so difficulty is held fixed while format varies; ANCOVA controls prior ability.

## SECTION — System internals & deployment (defer; open if asked)
## 14 — The system at a glance
**Background:** all on lab hardware, local 35B model, no paid API.
**Invites:** "Why local and not GPT-4?" Privacy, cost, reproducibility; the model only writes grounded prose.

## 15 — Request lifecycle
**Background:** know the endpoint flow: /analyze → workspace + seed + enqueue → /status polling → worker → perception → frozen analysis → subagents → /result.
**Invites:** "What does /status actually show?" A live feed parsed from the agent's event stream.

## 16 — Deployment & infrastructure
**Background:** five Compose services (caddy, api, redis, worker, beat); three hosts (app/GPU, tracker GPU, model GPU); state in Redis + on-disk workspaces.
**Invites:** "Does this scale?" The single-job limit is one GPU, not the design; add workers/GPUs to scale, jobs are already isolated.

## 17 — Agentic pipeline
**Background:** Steps 1–5 agentic (agent writes its own Python), Step 6 frozen, then A/B/D in parallel, then a figure-verification loop gates LaTeX. Tracker called once and cached.
**Invites:** "Why let the agent write code at all?" Perception is open-ended (arbitrary scenes); the agent adapts there. The physics is frozen precisely because it must not vary.

## (blackout) — three black slides
**Background:** intentional blank-screen buffer before the close. Advance through, or stop on one to pull the room's attention to you.

## 18 — Summary
**Background:** restate the one-liner and the four numbers. End by inviting discussion.
**Invites:** the open "so what's next / what worries you" question. Have the two honest limitations ready, that's the strongest way to close.

---

# BACKUP (after Summary, `\appendix`) — open if asked "how does it work?"

## B1 — Headline numbers
**Background:** the four numbers are a pilot (0.3% is one clip), a single clean clip (93.8%), material relevance vs an authentic textbook (0.840, 5 objects), and a structural fact (5 grounded sections, multimodal).
**Invites:** "How many clips is 0.3% based on?" Be honest: one so far, the pilot scales next. Don't oversell it as final.

## B3 — Three methods chained
**Background:** the colour split (code / model / stats) is the spine of the whole talk.
**Invites:** "Where exactly does the AI touch the numbers?" Answer: nowhere. It does perception and writes prose; every quantity is deterministic code.

## B4 — How the motion is measured
**Background:** the chain is track → fit circle → calibrate → differentiate. The "one ω drives everything" point prevents internal inconsistency.
**Invites:** "Why differentiate, doesn't that amplify noise?" Yes, which is why we smooth the angle first and median-filter ω after. The fit on the angle (an integral) is what we trust for classification.

## B5 — Measurement internals
**Background:** the slide a technical examiner will stop on. Know the constants: 8 px inlier band, 2.5σ outlier cut, window ≈ fps/6, gap fill ≤ 0.2 s, the two-condition centre rule.
**Invites:** "Why those thresholds?" Empirical and fixed in code for determinism; the centre rule's two conditions make the override self-guarding. "Why parabola vs line?" Constant α makes the angle quadratic, so a parabola beating a line by a large margin is the signature of non-uniform motion.

## B6 — Tracking → geometry (fan)
**Background:** the inward spiral is the doll swinging out as it speeds up, a physical effect, not tracking error.
**Invites:** "Is the spiral a tracking artifact?" No, it's real: faster spin, larger effective radius, then it settles. The dashed circle is the steady radius.

## B7 — Reproducibility by design
**Background:** the bad numbers (drifting formats, 1000 px drift) are the *rejected alternative's* behaviour, framed as motivation, not our history.
**Invites:** "But the tracker is non-deterministic, so how is it reproducible?" Split the stages: tracking once and cached, physics deterministic given the cached trajectory. The claim is about the physics module.

## B8 — Accuracy pilot
**Background:** ground truth is the turntable RPM, independent of both video and gyro. Summary stats first, then cross-correlation alignment.
**Invites:** "Why cross-correlation and not timestamps?" Phone clocks drift; cross-correlation aligns by the signal itself. "Sample size?" Pilot, expanding; this is the thesis's first experiment.

## B9 — Wording finding
**Background:** the detector is open-vocabulary, so wording is a real lever; 6% to 100%, and the best word differs per detector. The micro-sweep is **manual today** (we did it for the fan); automating it in the pipeline is roadmap, not built.
**Invites:** "Isn't that fragile for users?" Today the user names the object and we sweep a few words by hand on sample frames; the plan is to automate that so the user just names it once. Don't claim it's automatic yet.

## B10 — Robustness (centre + non-uniform)
**Background:** two model-mismatch failures, both fixed. Centre 158 px off → scatter 39% to 10%. Fan spin-up α=1.18, R²=0.9999.
**Invites:** "Could the override break a good human mark?" No: it needs a tight fit AND a big scatter reduction; a good mark already has low scatter, so it's kept. Verified across all ten clips, only the fan triggered it.

## B11 — Three regimes overview
**Background:** uniform / decelerating / accelerating, one pipeline, no tuning. This is the generalisation evidence.
**Invites:** "Only three objects?" They're chosen to span the three regimes deliberately; the point is the same code handles all three, not the count.

## B12–B14 — The three cases
**Background:** each "What the agent did" line is the agentic story: track → fit → classify, plus the fan's centre auto-correction. Bike uniform, turntable coast-down (α≈−4), fan spin-up (α=1.18).
**Invites (bike):** "Your ω plot isn't perfectly flat." True, it's near-constant; the line-vs-parabola test classifies it uniform because the curvature gain is small. **Invites (turntable):** "It speeds up then slows down." The captured run is dominated by the coast-down; the net fit is decelerating. **Invites (fan):** "How did you scale the fan?" The reference is the measured blade (47–50 cm long × 15 cm wide → ~0.32 m), giving orbit radius ~0.45 m and mean a_c ~21.8 m/s²; angular results (ω, α, T) are scale-free regardless.

## B15 — Kinematic readout
**Background:** θ → ω → a_c is one chain; the four panels cross-check. Curvature of θ = acceleration; slope of ω = α.
**Invites:** "How do these relate?" Walk the chain out loud: differentiate θ to get ω, its slope is α, square ω times r for a_c.

---

## Cross-cutting things to have memorised
- The reproducibility claim is about the **physics given the trajectory**, not the tracker.
- **Angular** results (ω, α, T) are exact; **metric** results (r, v, a_c) depend on the reference size.
- The centre override needs **two** conditions, which is why it's safe.
- Non-uniform motion is detected by a **parabola-vs-line fit on the angle**, not by thresholding noisy ω.
- BERTScore is for **comparability**, not quality; the reference is an **authentic OpenStax textbook** section, *reorganized* into our format (not the raw PDF, not paraphrased), built independently of our generation.
- The numbers most likely to be challenged: **0.3%** (one clip), **0.840** (material vs textbook, 5 objects), **21.8 m/s²** (fan mean a_c, from the measured ~0.32 m blade reference). Know the caveat for each.
- Don't name the prior method on stage — it's "the prior method" / "the prior sensor-based method".
