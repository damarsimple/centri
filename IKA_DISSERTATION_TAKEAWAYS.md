# What Centri can take from Utami's dissertation — reading & decision doc

> Source: *Authentic Math Word Problem Generation using Generative AI with
> Contextualization, Personalization, and Socialization* — Ika Qutsiati Utami, PhD
> dissertation, National Central University, advisor **Prof. Wu-Yuin Hwang**, Oct 2025
> (`Dissertation_Ika Qutsiati Utami_03102025.pdf`, 182 pp).
>
> This is the **direct parent line of Centri**: same lab, same advisor, same core thesis
> (authentic problems from real-world context via generative AI, three difficulty levels,
> multi-method evaluation). Her four studies: (1) SLR of MWP generation; (2) **Geo-QG** —
> mobile object-recognition + AR-Core measurement + GPT-3.5, 3 tiers; (3) quasi-experiment
> on effectiveness; (4) **SocioMathLLM** — prompt-engineered group-socialization MWPs.
>
> **Status:** drafted for you to read. Decisions on #2/#3/#4 pending your review. #1 and #5
> already agreed. See also [[PAPER_GAP_ASSESSMENT]] and [[MATERIAL_REWORK_STATUS]].

---

## 1. Adopt her evaluation method (agreed) — optimized for our use case

**Her method (dissertation §2.4, §3.2.4, §3.4.3, Figs 12 & 15).** Three axes, then correlate:

- **Automatic** — BLEU (n-gram precision) + STS (semantic textual similarity) in Study 2;
  BLEU + **BERTScore** (precision/recall/F1) in Study 4. She uses STS two ways: *relevancy*
  (input-prompt vs generated output, higher = better) and *diversity* (avg pairwise STS
  across generated items, **lower = more diverse**). BLEU is read on an interpretation scale
  (her §3.2.4): <1.0 undesired, 3.0–4.0 understandable, 4.0–5.0 high quality, 5.0–6.0 very
  high, >6.0 better-than-human.
- **Human (expert teachers)** — a 5-point rubric on two aspects (Study 2 §3.2.4) with
  inter-rater reliability via **Cohen's κ + % agreement**:
  - *Linguistic*: relevance, language fluency, comprehensibility, linguistic complexity,
    completeness.
  - *Mathematical*: answerability (solvability + #corrections), mathematical applicability,
    difficulty level, realistic level.
  - Study 4 refines these into **developed-criteria tables** (Tables 8/9/10): *authenticity/
    linguistic* = motivating context, language/cultural clarity, appropriate #solution-steps,
    variety of solution strategies, cognitive demand; *mathematical* = answerability,
    structure & clarity, multiple solution strategies.
- **LLM-as-judge** (Study 4) — the model scores each item on the **same rubric**, and
  human–LLM agreement is reported via **ICC** (Intraclass Correlation Coefficient). She also
  cites G-Eval (CoT prompting) and notes LLMs' positional/format biases.
- **Correlation** — Pearson between automatic and human scores (Study 2 RQ3); ICC for
  human-vs-LLM (Study 4).
- Scale: 10 teachers / 200 generated problems (Study 2); 5 teachers (Study 4).

**How Centri adopts + optimizes (the "our use case" part).** Her unit is a *question*
(text-vs-text, 2-column Colab); ours is a **learning-material passage** (PDF-vs-PDF, three
tiers). So:

1. **Keep for comparability:** BLEU/ROUGE + **BERTScore** (we already emit these in
   `run_material_eval.py`), STS relevancy+diversity split, Pearson (auto vs human), ICC
   (human vs LLM). Reporting these = our numbers sit next to the lab's published ones.
2. **Copy her rubric dimensions verbatim into `run_llm_judge.py`** (Tables 8–10). Today our
   judge criteria (relevance, answerability, difficulty-fit, concept accuracy, annotation
   accuracy) are *close* but not identical — align them exactly so a reviewer sees continuity.
3. **Optimize for tiers + physics:**
   - Add a **difficulty-fit / achieved-Bloom** dimension per tier (we already have EI + Bloom
     labels from the gate — feed them as ground truth to the judge).
   - Add a **grounding/answerability** dimension the judge can check against the seed numbers
     (our gate already does the deterministic version; the judge does the semantic version).
   - **Tier-matched references** (already decided, spec §9 option b) instead of one fixed
     reference — removes the lexical-density confound her single-reference setup would hit.
   - Our **deterministic gate is an extra intrinsic axis she doesn't have** — keep it as a
     first-layer, zero-cost pedagogy-aware signal, then her three axes on top.
4. **Primary vs comparability:** we argue (as in PAPER_GAP) that BLEU/BERT are weak proxies
   for pedagogy, so **LLM-judge + teacher rubric are the headline**, BLEU/BERTScore the
   comparability baseline. She effectively does the same in Study 4.

**Net:** her method is the template; we keep her metrics for comparability, swap her
question-rubric for her own material/criteria tables, add tier-awareness and our gate.
This is mostly a `run_llm_judge.py` rubric edit + running the tier-matched eval — no new
methodology to invent.

---

## 2. CoT candidate-selection generation loop (reading primer — decide after)

**Why you're reading this:** it's the principled fix for the documented **35B
self-correction limitation** (the model re-emits or trades banned words on regen instead of
fixing them — see [[MATERIAL_REWORK_STATUS]] §"35B limitation"). Her SocioMathLLM uses a
*generate-review-select* loop that plays to a small model's strength (drafting) and around
its weakness (self-correcting).

### How her loop works (dissertation §3.4.1, Figs 16 & 18)
Three modules, each a distinct prompting strategy:

1. **Contextualization module — generate breadth.** Zero-shot prompt with authentic context
   (image + text) + authenticity criteria → the model produces **5 candidate MWPs**. The
   point is *variety*, not correctness yet.
2. **Personalization module — review & select.** The 5 candidates are fed back with
   **Chain-of-Thought (CoT)** prompting + the student-persona background + the mathematics
   criteria. The model **reviews each candidate step-by-step, scores them, and selects the
   single best one** with a rationale. This is the key move: *selection among drafts*, not
   *correction of one draft*.
3. **Socialization module — refine.** The selected MWP is refined with **few-shot** prompting
   (worked examples of the desired style) into the final variants.

So the pattern is: **breadth (N candidates, zero-shot) → judge (CoT review, pick 1) → polish
(few-shot refine).** Contrast with Centri today: a single draft, then *blind/failure-informed
re-roll* if it fails the gate — which the 35B does badly.

### Why selection beats correction for a small model
- Drafting is a **forward** task (the model is good at it); self-correction is a **meta**
  task (reason about your own error and surgically fix only it) — sparse-MoE 35B models are
  weak at the meta task, strong at the forward one.
- Generating 3–5 independent drafts and keeping the cleanest is a **variance-reduction**
  strategy: if any single draft has a ~50% chance of a stray vocab flag, the best of 4 is
  clean with high probability — *without* asking the model to reason about its mistake.
- CoT review makes the *selection* explicit and inspectable (why this candidate), which is
  itself a quality signal and aligns with the LLM-judge we're building anyway.

### How Centri would implement it (concrete, if you choose this)
Minimal version, reusing what exists:
1. Per tier, **generate K drafts** (K≈3) in parallel-ish (K calls) with the current prompt.
2. Run **all K through the existing `material_gate`** — we already have the deterministic
   verdict for free.
3. **Select** the draft with zero issues; tie-break by fewest-issues, then by an optional
   CoT-review call (or the LLM-judge rubric) for pedagogy.
4. Only if *all* K fail, fall back to the current best-of-N regen.

Fuller version (closer to hers): add an explicit CoT-review call that scores the K candidates
on the rubric and picks one, so selection is pedagogy-aware not just gate-aware.

### Tradeoffs to weigh (this is your decision)
- **Cost/latency:** K× the generation calls per tier (3 tiers × K). At ~7–11 s/call and
  ~355 tok/s locally, K=3 roughly triples material-gen time per job (still seconds–minutes,
  and we own the GPU, so arguably fine).
- **Determinism:** selection adds a choice step; keep it reproducible (fixed seed/temperature,
  deterministic tie-break) so "same video → same material" still holds.
- **Complexity:** modest — it's a loop around the existing `_generate` + `tier_gate`, not a
  new subsystem. The hints file + best-of-N stay as the first-pass steer and the fallback.
- **Payoff:** most likely gets us from 13/15 clean tiers to ~15/15 on stochastic runs, i.e.
  actually reaching the "zero vocab hits" target without a bigger model.

**Decision framing:** do we (a) ship as-is (proceed-but-flag already never hard-blocks, output
is good), (b) do the minimal generate-K-gate-select, or (c) the full CoT-review select? My
lean is (b) — biggest robustness gain for least complexity — but it's genuinely your call
after weighing the K× cost.

---

## 3. Positioning / contribution framing from her SLR (reading — decide after)

**Why you're reading this:** it's how we frame Centri's novelty in the paper's (currently
skipped) Background/Related-Work, using her SLR as the map of the field.

### What her SLR found (dissertation §4.1, Figs 19–21, 28 studies 2015–2025)
- **Topic split:** arithmetic **50%**, algebra 25%, **geometry 11%**, speed-distance-time 7%,
  probability 3%. Physics/kinematics is essentially absent.
- **Difficulty levels are rare:** only **3 of 28** studies generate with explicit difficulty
  levels.
- **Input modality:** *every* study uses text as input; a handful use images (AR/photos). She
  recommends multimodal (image+text) as a future direction. **None measure kinematics from
  video CV.**
- Generation methods: template-based, question-rewriting, neural (encoder-decoder), and
  recently LLM/generative-AI — but only Christ et al. 2024 & Xie et al. 2024 use LLMs for
  MWP, and neither does contextualization/personalization/difficulty jointly.

### The contribution hook this hands us
Centri sits in a **genuinely open niche**: *video-CV-measured, difficulty-tiered physics
material.* The crisp contrast to write:
- **Sensing:** she acquires context via object recognition + **AR-Core measurement** (and the
  parent P-MAGIC line uses a **phone IMU** bolted to the object). Centri measures the **real
  object's motion from ordinary video** — nothing attached, no AR session, works on any clip.
- **Domain:** she does geometry (static shapes, area/perimeter/volume); Centri does
  **kinematics** (a *dynamic* quantity — angular velocity, acceleration, spin-up), which is
  why the measurement problem is harder and the video approach earns its keep.
- **Difficulty:** we're in the rare 3/28 that tier by difficulty, and we tier *depth*
  (idea → relations → dynamics) grounded in Bloom+CLT, with a deterministic cross-tier gate
  no prior work has.
- **Determinism:** our physics is frozen/seeded (byte-identical), unlike LLM-authored
  numbers — a reliability property the field's neural methods lack.

**One caveat to be honest about:** her difficulty semantics are *structural* (easy = one
object; intermediate = compare two; advanced = compound shape) while ours are *depth-based*.
Worth a sentence mapping the two so a reviewer from her line isn't confused.

---

## 4. Effectiveness-study blueprint from her Study 3 (reading — decide after)

**Why you're reading this:** the effectiveness study is Centri's **biggest gap**
([[PAPER_GAP_ASSESSMENT]] §"Evaluation"), and her Study 3 is a ready-made, teacher-approved,
publishable design we can replicate rather than invent.

### Her design (dissertation §3.3, Figs 13–14, Tables 3–6)
- **Participants:** 51 fifth-graders (after 1 dropout), two classes, EG vs CG, ~26 each,
  different teachers (>10 yrs experience), mean age 10.5.
- **Procedure (6 weeks):** Wk1 train on the app; Wk2 **pre-test** (teacher-validated,
  8 open-ended items in 3 categories); Wk3–5 learning (EG uses the system with contextual/
  personalized MWPs; CG uses textbook MWPs); Wk6 **post-test** + questionnaire + interviews.
- **Instruments:** pre/post geometry word-problem tests (different items, matched difficulty,
  to block memorization); **TAM questionnaire** (5 subscales: perceived use, utility,
  playfulness, intention, attitude; 15 items, 5-point Likert; validity via CVR>0.79,
  reliability via Cronbach's α); structured interviews (10 students, 5 high / 5 low
  achievement).
- **Analysis:** normality → parametric; One-Way ANOVA (group means), **ANCOVA** on post-test
  with **pre-test as covariate** (reduces bias, the key move), Pearson (behavior ↔
  performance), **stepwise regression** for the strongest predictor of learning performance;
  qualitative narrative analysis of interviews.
- **Logged learning-behavior variables (Tables 3–5)** — a template for what our app should
  record: problem-context understanding, identifying contextual info, **visual-schematic
  representation quantity & quality** (per difficulty level), math-concept application,
  solution agreeability, reflection on past learning / on learning analytics.
- **Performance variables (Table 6):** total score + per-category (single-shape, comparison,
  compound) scores.

### How Centri maps onto it
- EG = Centri-generated tiered physics material; CG = textbook circular-motion problems.
- Pre/post = physics problem-solving items (matched difficulty), teacher-validated.
- Replicate ANCOVA(pre-test covariate) + Pearson + stepwise regression; add per-tier scores
  (basic/intermediate/advanced) as the per-category analogue.
- **App instrumentation to add** (so the behavior analysis is possible): log per-tier attempts,
  correctness, the student's own working (our app already has an annotate/whiteboard analogue),
  and reflection/analytics views — mirroring her Tables 3–6.
- Reuse her TAM questionnaire (it's from Hwang et al. 2020 — same lineage) so acceptance
  numbers are comparable.

**This is a later, resource-heavy push** (needs students + teachers + IRB/consent), but having
her exact design means we don't design from scratch — we adapt.

---

## 5. What NOT to copy (agreed)
Her Study 4 **socialization / group-MWP** work (collaboration/cooperation/negotiation/
ideas-sharing, the 5W1H social-criteria table, few-shot guided discussions) is *her* novel
contribution. Centri shouldn't duplicate it — it would blur our story. Our parked Socratic
tutor could integrate socialization *later*, but it's not our lane now. Her template/AR-Core
specifics also don't transfer (different domain, different sensing).

---

## Suggested sequencing (my lean — for when you've read the above)
1. **#1 now** — align `run_llm_judge.py` to her rubric tables + run the tier-matched eval so
   the paper's Results has real, comparable numbers. (Low effort, unblocks the paper.)
2. **#2 next** — prototype generate-K-gate-select (minimal version) as the durable answer to
   the 35B limitation. (Medium effort, the one open technical thread.)
3. **#3 with the paper** — write Background/Related-Work using her SLR to stake the
   video-measurement + difficulty-tier novelty.
4. **#4 later** — the effectiveness study, using her Study 3 as the blueprint.
