# Centri — glossary to memorise

Terms you'll either say or be asked about. Each entry: a plain definition, then the Centri-specific value or context where it matters. Memorise the bold short form first.

---

## Physics of circular motion

**Angular velocity (ω).** How fast the angle changes, in radians per second. *Centri: the one series everything else is derived from. Bike ≈ 5.1, fan ramps 3.2 to 10.2.*

**Angular acceleration (α).** How fast ω itself changes, in rad/s². Zero for steady spin, positive for speeding up, negative for slowing down. *Centri: fan +1.18, turntables ≈ −4. Detected by fitting the angle to a parabola.*

**Tangential speed (v).** Linear speed along the circle, v = ω·r. Metres per second.

**Centripetal acceleration (a_c).** The inward acceleration that keeps something on a circle, a_c = ω²·r. Points toward the centre. *Grows with the square of ω, which is why a speeding-up fan has a sharply rising a_c.*

**Tangential acceleration (a_t).** The along-the-circle acceleration from changing speed, a_t = α·r. Zero for uniform motion. *Centri reports this now for the non-uniform cases; total acceleration is √(a_c² + a_t²).*

**Period (T) and frequency (f).** Time for one revolution, and revolutions per second; T = 2π/ω, f = 1/T. *Fan T ≈ 0.91 s, f ≈ 1.1 Hz.*

**Uniform vs non-uniform circular motion.** Uniform means constant ω (only a_c). Non-uniform means ω is changing (a_c and a_t both present). *The three cases are exactly uniform, decelerating, accelerating.*

**Radius (r).** Distance from the rotation axis to the object. *Comes from the fitted circle, converted to metres via calibration.*

---

## Computer vision and measurement

**Open-vocabulary detector.** A model that finds an object from a free-text description instead of a fixed label set. *Why we can track arbitrary objects with no per-object training; also why wording matters.*

**SAM3.** The segmentation-and-tracking model we run in production, on its own GPU. Called once per video, then cached.

**Trajectory.** The object's centre position in every frame. The raw input to all the physics.

**RANSAC.** A robust fitting method: repeatedly fit from a small random sample, keep the model the most points agree with, discard the rest as outliers. *We use it to fit the orbit circle so a few bad frames can't distort it.*

**Circumcircle.** The unique circle through three points. *RANSAC's per-iteration sample is three trajectory points.*

**Inlier / outlier.** Points that do (or don't) fit within a tolerance of the model. *Inlier band is 8 px; points beyond 2.5σ in radius are dropped.*

**Residual.** How far the data sits from the fitted model. Low residual means a good fit. *Fan orbit residual ≈ 1.6%.*

**Coefficient of variation (CV).** Standard deviation divided by mean; a unitless "how wobbly." *Radius CV is our centre-quality check: fan went 39% to 10% after the centre fix.*

**Centre drift.** Distance between the human-tapped axis and the fitted axis. *Fan drift was 158 px, which triggered the override.*

**Calibration (px_per_m).** Pixels per metre, from a reference object of known size: diameter in pixels divided by real size in metres. *The one place real-world scale enters; the fan uses the measured blade (47–50 cm long × 15 cm wide → ~0.32 m), giving orbit radius ~0.45 m.*

**unwrap / atan2.** atan2 gives the angle of a point; unwrap removes the ±π jumps so the angle grows smoothly across revolutions. *Needed before differentiating to get ω.*

**Savitzky–Golay filter.** A smoothing filter that fits a small local polynomial; smooths without flattening real trends. *Applied to the angle before differentiating, window ≈ fps/6.*

**Median filter.** Replaces each value with the local median; kills isolated spikes. *Applied to ω after differentiation.*

**Coverage.** Fraction of frames where the object was successfully tracked. *Bike 93.8%, fan and turntables 100%.*

---

## NLP and evaluation

**Contextual embedding.** A vector for a word that depends on its sentence, so the same word in different contexts differs. *The basis of BERTScore; lets "wheel" and "tyre" score as similar.*

**RoBERTa.** The pretrained language model whose embeddings BERTScore uses.

**BERTScore (P, R, F1).** Match each token of the candidate to its most similar token in the reference by cosine, then average. Precision is over candidate tokens, recall over reference tokens, F1 is their harmonic mean. *Our material vs the OpenStax §6.2 reference (authentic textbook reorganized into our sections, not the raw PDF): whole-passage F1 0.840 ± 0.002 across 5 runs (3 phenomena: turntable ×3, bike, fan). Kept for comparability, not as a quality claim — the quality eval (judge + teachers) is designed but not yet run.*

**Semantic textual similarity (STS).** How close two sentences are in meaning, via sentence embeddings.

**Sentence-transformer.** A model that embeds a whole sentence into one vector. *Used for the diversity score.*

**Cosine similarity.** Angle-based similarity between two vectors, 1 is identical, 0 is unrelated.

**Diversity score.** One minus the average pairwise similarity within a set of passages; higher means more varied. *0.204 across our 5 materials — low by design — the passages share one topic and structure — so the material eval leads with BERTScore relevance, not diversity.*

**LSTM fluency score (prior method).** A language-fluency score from the prior method's own trained LSTM model — the fifth metric in their Table 3. *We do not report it: we lack their trained model, and we won't substitute a different, non-comparable proxy. We reproduce the other four (BERT P/R/F1 + diversity).*

**BLEU.** N-gram precision overlap between candidate and reference. *On the "next plan" slide as a metric to add; lexical, so paraphrased material scores low by nature.*

**ROUGE-1/2/L.** Recall-oriented n-gram / longest-common-subsequence overlap — how much of the reference content appears in the output. *Planned addition for coverage.*

**BLEURT.** A learned (model-based) evaluation metric trained to predict human quality judgements of a candidate against a reference. *Planned addition; gets closer to quality than raw similarity.*

**LLM-as-judge.** Using a language model to score answers against a rubric for correctness and pedagogical quality. *A cross-check, not the final word; the teacher panel is the authority.*

**Cohen's / Fleiss' kappa (κ).** Inter-rater agreement corrected for chance; Cohen's for two raters, Fleiss' for many. *For the 10-teacher panel.*

**ANOVA.** Tests whether group means differ across conditions. *For comparing across difficulty × format conditions.*

**ANCOVA.** ANOVA with a covariate removed first. *Learning study: compares post-test scores controlling for the pre-test.*

**Pearson r.** Linear correlation, −1 to 1. *Used for video-vs-gyroscope agreement and for automatic-vs-human score agreement.*

**Effect size (Cohen's d, η²).** How big a difference is, not just whether it's significant. *Reported alongside the learning-study p-values.*

---

## System and infrastructure

**Agent (`pi`).** The orchestrator that runs inside each job: it writes and runs its own Python for perception, then calls the frozen physics module.

**Frozen / seeded module.** The deterministic physics code (`analysis.run`), copied identically into every job so the agent can't alter it. *The reason "same video, same numbers" holds.*

**Workspace.** A self-contained folder per job holding the video, the seeded code, and all outputs. *Isolation, and what gets cleaned up on a timer.*

**FastAPI.** The Python web framework serving the REST API (`/analyze`, `/status`, `/result`).

**Celery.** The task queue that runs jobs in the background; our worker runs one at a time.

**Redis.** In-memory store used both as the Celery broker and to hold job status and results.

**Docker Compose.** Defines and runs all the services together (caddy, api, redis, worker, beat).

**Caddy.** Reverse proxy handling TLS and the public endpoint.

**beat.** The Celery scheduler; here it expires old workspaces hourly.

**Qwen3 35B.** The local 35-billion-parameter language model, on its own GPU, that writes the learning material.

**Subagents A / B / D.** Parallel helpers after the physics: A renders the annotated video, B the figures (seeded code, then visually checked), D writes the learning material from a deterministic seed (the only true LLM author). (Subagent C generates practice questions; it still runs but is not featured in this material-focused talk, hence the gap in the letters.)

---

## Study-design terms

**Pre-test / post-test / retention test.** Measure before, immediately after, and later, to capture both learning and whether it sticks.

**Covariate.** A variable controlled for, here the pre-test score.

**Multimodal ablation.** The comparison that turns a modality on or off (text-only vs text-plus-visual) to isolate its effect. *Enabled by the material spanning image / graph / table / text per scene.*

**Cognitive load.** Mental effort a task demands, measured with a standard questionnaire.

**The prior method.** The published, sensor-based (gyroscope-app) method we align with and compare against — the baseline for the joint study. *Referred to only as "the prior method" in the deck; don't name it on stage.*
