# Centri positioning & related work — framed against Utami's SLR

Feeds the paper's (currently skipped) Background / Related-Work section. Uses Utami's systematic
literature review as the map of the math-word-problem-generation field and stakes Centri's niche
against it. Source: Utami (2025) §4.1, Figs 19–21 — an SLR of 28 studies (2015–2025).

## What the field looks like (her SLR)

- **Topic split:** arithmetic **50%**, algebra 25%, **geometry 11%**, speed-distance-time 7%,
  probability 3%. Physics / kinematics is essentially absent.
- **Difficulty levels are rare:** only **3 of 28** studies generate with explicit difficulty
  levels.
- **Input modality:** *every* study takes text as input; a handful add images (AR / photos).
  She recommends multimodal (image+text) as future work. **None measure kinematics from video
  computer vision.**
- **Generation methods:** template-based, question-rewriting, neural encoder-decoder, and
  recently LLM/generative-AI — but only Christ et al. 2024 & Xie et al. 2024 use LLMs for MWP,
  and neither does contextualization + personalization + difficulty jointly.

## Centri's niche (the contribution hook)

Centri occupies a genuinely open cell: **video-CV-measured, difficulty-tiered physics material.**
The crisp contrasts to write:

- **Sensing.** Utami acquires context via mobile object-recognition + **AR-Core measurement**;
  the parent P-MAGIC line bolts a **phone IMU** to the object. Centri measures the **real
  object's motion from ordinary video** — nothing attached, no AR session, works on any clip.
- **Domain.** She does geometry (static shapes: area / perimeter / volume). Centri does
  **kinematics** — a *dynamic* quantity (angular velocity, acceleration, spin-up) — which is why
  the measurement problem is harder and the video approach earns its keep.
- **Difficulty.** Centri is in the rare 3/28 that tier by difficulty, and it tiers *depth*
  (idea → relations → dynamics) grounded in **Bloom + Cognitive Load Theory**, with a
  deterministic cross-tier gate no prior work has.
- **Determinism.** Centri's physics is frozen/seeded (byte-identical numbers), unlike
  LLM-authored quantities — a reliability property the field's neural methods lack.

## The video line — our own literature review (2026-07-08)

Her SLR maps the *problem-generation* field; it does not cover the **video** angle, and neither
parent work senses from video (Utami = AR-Core, P-MAGIC = phone IMU). A targeted search of the
video-based-recognition-for-physics literature places Centri precisely:

- **Video analysis is established physics-ed pedagogy — but manual.** Tracker / Open Source Physics
  (arXiv:1207.0220), PhysMo, FizziQ, and Tracker-for-kinematics studies (*Momentum* J., the same
  Indonesian SMA context P-MAGIC targets) all have the *student* mark points frame-by-frame. The
  tool measures; none generate material.
- **CV object tracking exists only as a teaching *aid*.** Computer-Vision Object Tracking for HS
  Physics (IEEE, 2017) reaches r = 0.99 vs theory on a pendulum — but a single-experiment
  measurement aid, not authentic, tiered, or generative.
- **Video → question generation is emerging — for lecture *content*, not motion.** VLMs generating
  questions from educational videos (arXiv:2505.01790), Context-Selection video QG (arXiv:2504.19406),
  the AQG survey (Springer, 2021). These read lecture frames + transcript and **explicitly struggle
  with difficulty control** (2505.01790: inter-rater 0.43 on difficulty, mostly shallow "what/recall"
  questions). Centri extracts **physics measurements from motion** and controls difficulty
  deterministically — the exact gap they flag.
- **AI physics-video is active — but the *opposite* direction.** Physics-aware video *generation*
  (DiffPhy, arXiv:2505.21653), the PhyEduVideo text-to-video benchmark (arXiv:2601.00943),
  MM-PhyRLHF (arXiv:2404.12926). State plainly that Centri is **video → understanding → material**,
  the inverse of the text→video crowd, so it is not mistaken for it.

**Sharpened niche (one sentence):** video analysis is *manual*, CV tracking is a *measurement aid*,
VLM-QG is for *lecture content* — **no one generates grounded, difficulty-tiered physics learning
material from motion-video recognition.**

## Hard differentiation from P-MAGIC (same lab — must be explicit)

P-MAGIC (Hwang, Sari, Purba, Azhar, *J. Educational Computing Research* 2026, `document-4.pdf`) is
the *direct sibling*: same advisor, also multimodal, and it **already does automated annotation**
(radius/ω/a_c arrows on a still image via Hough + OpenCV; increase/steady/decrease phase labels on
graphs and tables). So multimodality and annotation are **not** Centri's novelty versus the parent
line. Centri must lead on what genuinely differs:

- **Input:** ordinary **video / CV tracking**, nothing attached — vs P-MAGIC's on-object phone IMU
  (accelerometer + gyroscope). More ubiquitous and authentic.
- **Output:** difficulty-tiered learning **material** (exposition) — vs word **problems**.
- **Grounding:** a deterministic grounding gate verifying every number against ground truth —
  P-MAGIC has no equivalent.
- **Annotation, but on video:** per-frame annotation across the *motion*, not one still image + a
  sensor graph. P-MAGIC's own ablation shows annotation matters (annotated ≫ non-annotated,
  Cohen's *d* up to 1.7), which motivates doing it well on video.

## The honest caveat (write this so a reviewer from her line isn't confused)

Her difficulty semantics are **structural** (easy = one object; intermediate = compare two;
advanced = compound shape). Centri's are **depth-based** (basic = one idea, no equations;
intermediate = coordinate a few relations; advanced = integrate change-over-time). Both are
valid difficulty ladders; they are not the same axis. One sentence mapping the two belongs in the
paper.

## One-line framing for the abstract

> Prior automatic MWP generation is dominated by arithmetic/geometry, text-only input, and flat
> difficulty; Centri generates **difficulty-tiered physics** material from **quantities measured
> directly in video**, with a deterministic grounding gate — a cell the field's 28-study record
> leaves open.
