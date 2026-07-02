# Paper 2 / Stage 2 — Authentic Learning Materials & Their Influence on Learning

Planning doc for the **second study**: moving from "we can generate good material"
(paper 1) to "students learn from it" (paper 2). Sources: Prof. Hwang's messages in
`chat-log.txt` + the P-MAGIC paper (`document-3.pdf`). Companion to
[SESSION_CHECKPOINT.md](SESSION_CHECKPOINT.md) and [PAPER_GAP_ASSESSMENT.md](PAPER_GAP_ASSESSMENT.md).

> **Two-bucket convention below:** **[PROF]** = something the professor explicitly asked
> for (traceable to chat-log). **[CONSIDER]** = my suggestion / open design question for
> you to decide with him and Vinsa. Don't attribute [CONSIDER] items to the prof.

---

## 1. The professor's vision (from chat-log)

- **[PROF]** Working title: *"AI-based authentic learning materials generation in real
  worlds and its influence on learning."* Target venue: **IEEE Transactions on Learning
  Technologies**, as a **pilot experiment**.
- **[PROF] Two evaluations of the generated learning materials:**
  1. **Material quality** — accuracy and difficulty levels (this is paper-1 territory).
  2. **Student study** — let students learn from the generated materials, then evaluate
     **perceptions (usefulness, playfulness, attitude, motivation)** *and* their
     **learning improvements**.
- **[PROF] Learn-by-manipulation**: "ask students to rotate the turntable with different
  forces and teach centripetal acceleration through demonstrating the different results
  with radius, angular velocity and force." Learners understand the concept "with their
  self experiences."
- **[PROF] "What you see, what you learn"** through manipulating the real phenomenon and
  studying the authentic contextual learning contents.
- **[PROF] Multimodal contents** = text, graphs (acceleration, velocity…), annotated video
  (r, a_c, ω) — generated *first*; physics problems generated *after*.
- **[PROF] Human-in-the-loop** is required where full automation can't deliver — and
  feedback must be *meaningful* even when a student is *partially* correct (not just
  right/wrong).
- **[PROF] Topics**: centripetal acceleration **first**, then **simple pendulum** (the
  Thailand intern is on pendulum video recognition — possible collaboration / 2nd topic).
- **[PROF] Bicycle = richer case**: two rotations (pedal + wheel); recognize both and
  explore the relationship between the two centripetal-acceleration phenomena.
- **[PROF] Learners**: high-school students (vocational or normal), possibly in **Jogja**;
  recruit via Vinsa's contacts (she has SMA teacher contacts).
- **[PROF] Reliability first**: improve recognition robustness (lighting, right-angle
  video) *before* deploying to students; HITL as the safety net.
- **[PROF] Dropped**: Manim/animation video ("too complicated") — keep demonstrations
  simple.
- **[PROF] Future / "next version"**: self-improving loops — a "smart and automatic
  contextual learning materials/problems generator."

## 2. What paper 2 adds over paper 1

| | Paper 1 (now) | Paper 2 (this doc) |
|---|---|---|
| Claim | system *generates* quality material | students *learn* from it |
| Evaluation | material quality (BERT/diversity + teachers) | + student perceptions + learning gains |
| Subjects | teachers (raters) | **real students** (high school) |
| Flow | generate → artifacts | **manipulate → observe → study → practice → feedback** |
| Pedagogy | passive, single-instance | interactive, multi-condition, scaffolded |
| Venue | (JECR-style quality study) | **IEEE TLT** (learning-effect study) |

## 3. Study design — to think about

### Research questions [CONSIDER, aligned to PROF's two evals]
- RQ1: Does learning with the authentic, AI-generated material improve students'
  understanding of centripetal acceleration (pre→post)?
- RQ2: How do students perceive it — usefulness, playfulness, attitude, motivation?
- RQ3 (optional): Does *manipulation/comparison* (two forces) beat passive consumption?
- RQ4 (optional): Do effects hold across topics (centripetal → pendulum)?

### Design [CONSIDER]
- **Quasi-experiment, pre/post test** (the prof's "pilot experiment").
- A **control condition** strengthens the learning claim. Options:
  - generic/textbook material vs our authentic material, OR
  - our material *without* manipulation vs *with* manipulation (two-force comparison).
  Pick one comparison you can actually staff — a single-group pre/post is the minimum but
  weaker for IEEE TLT.
- Watch the **novelty effect** (cool app ≠ learning) — hence pre/post + control.

### The learning activity flow [CONSIDER — operationalizes PROF's "manipulation"]
A concrete session a student does:
1. **Manipulate**: spin the turntable with a *soft* then a *hard* push (or two radii).
2. **Capture**: record each; system measures r, ω, a_c (HITL annotate as needed).
3. **Observe/compare**: generated material *contrasts the two conditions* → shows
   `a_c ∝ ω²` / effect of force. (This is the multi-condition upgrade noted in the
   checkpoint — paper 2 *needs* it; a single clip can't teach a relationship.)
4. **Study**: annotated video + graph + table + text, with scaffolding linking the
   representations.
5. **Practice**: the 3-tier question bank (advanced tier now compares the two real
   conditions, not stale within-clip phases).
6. **Feedback**: the Socratic tutor gives *meaningful, partial-credit* feedback [PROF].

### Participants & logistics [CONSIDER]
- Sample size for a pilot (e.g. 20–40+; enough for the chosen stats).
- Recruitment via Vinsa's SMA contacts; site (Jogja?); consent / IRB (P-MAGIC had IRB).
- Session length, devices, offline/local operation, who runs the annotation (student vs
  facilitator), one-object vs two-object sessions.

## 4. Measures & instruments [CONSIDER — map to PROF's named constructs]
- **Learning gains**: validated pre/post concept test on centripetal acceleration
  (normalized gain / paired t-test / ANCOVA on prior knowledge).
- **Perceptions** (the prof named these — likely existing validated scales in his line of
  work; confirm which he wants):
  - **Usefulness** → TAM perceived usefulness (+ ease of use).
  - **Playfulness** → perceived playfulness / flow.
  - **Motivation** → ARCS or a learning-motivation scale.
  - **Attitude** → attitude-toward-using / toward-physics scale.
- **Process/behavior**: HITL correction rate, time-on-task, number of manipulations,
  tutor interactions — cheap to log, strengthens the story.
- **Reliability/validity** of instruments: Cronbach's α; report like paper 1's κ.
- **Knowledge graph of student understanding** [PROF 2026-06-25, ask Vinsa — defer here]:
  represent the concept as a small KG with nodes/edges tiered **easy / intermediate / hard**
  (mirrors our 3-tier material/question difficulty: recall → apply formula → analyse/compare).
  Use it to (a) *diagnose* which sub-concepts a student has vs misses (map pre/post responses
  and tutor turns onto KG nodes), and (b) *sequence* material adaptively. The 3 tiers already
  map cleanly onto KG depth, so the generated material/questions can be tagged to nodes.
  **Open**: whose KG ontology (build vs reuse), how to score node mastery, manual vs
  LLM-extracted mapping. Coordinate with Vinsa; **deferred to Paper 2** (not Paper 1).

## 5. Product prerequisites before students touch it [CONSIDER]
- **Recognition reliability** up from ~50% on hard clips [PROF: "improve reliability first"].
- **Multi-condition comparison** capability (two clips → comparative material). Highest
  leverage; needed for both the pedagogy and the advanced question tier.
- **Tutor integrated** into the material flow (currently parked) with partial-credit
  feedback [PROF].
- **HITL UX** smooth enough for a student/facilitator (annotate screen).
- **Right-angle/quality video guidance** in-app [PROF: video quality is essential].
- Stable, **offline/local** deployment (Qwen3) for a classroom.

## 6. Topics & scope [PROF]
- **Centripetal acceleration first** (turntable; bicycle as the richer two-rotation case).
- **Simple pendulum second** — coordinate with the Thailand intern (pendulum recognition);
  a 2nd topic supports a generalizability claim.

## 7. Open decisions to settle (with Prof & Vinsa)
1. Control condition: which comparison (authentic-vs-generic, or with-vs-without
   manipulation)? Or single-group pilot?
2. Exact perception instruments (which validated scales the prof wants to reuse).
3. Site, sample size, timeline; IRB/consent route.
4. One topic (centripetal) for the pilot, or centripetal + pendulum?
5. How much manipulation is student-driven vs facilitator-driven.
6. Division of labor: Vinsa (eval/teachers/students), Damar (system/measurement), intern
   (pendulum).
7. **Knowledge graph** (PROF 2026-06-25): adopt a tiered KG for understanding/diagnosis +
   adaptive sequencing? Whose ontology, node-mastery scoring — ask Vinsa. (See §4.)

## 8. Risks / threats to validity [CONSIDER]
- **Recognition unreliability** breaks the student session → HITL fallback mandatory.
- **Novelty effect** inflates perceptions → control + pre/post.
- **Small pilot N** → frame as pilot, report effect sizes, don't over-claim.
- **Calibration accuracy** (esp. hard scenes like the fan) → trustworthy numbers are the
  whole premise; lean on paper-1 sensor-parity result.
- **Claims hygiene**: only claim learning effects you measured; keep "authentic material"
  and "improves learning" as separately evidenced.

## 9. Sequencing relative to paper 1
- Paper 1 = sensor-parity + material-quality (JECR-style). Finish first; it's the
  credibility anchor.
- Paper 2 = this study (IEEE TLT). Gate it on: reliable recognition + multi-condition
  comparison + integrated tutor + a recruited cohort.
