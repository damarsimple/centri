# LLM-judge reliability — two raters on one rubric (2026-07-31)

> ⚠ **FROZEN RECORD — superseded 2026-08-06.** Everything below describes the **7-clip / n = 21**
> corpus. That corpus no longer exists: `fan-4027`, `fan-4028` (synthesized orbits) and
> `turntable-3` (tracker teleports) were withdrawn and `fan-4656` added, so the corpus is now
> **5 clips / n = 15**. The re-measured numbers are **κ = 0.31 quad / 0.14 unweighted over 180
> pairs**, `cognitive_demand` **κ = 0.70** (best-agreed), `grounding_accuracy` **κ = −0.07** with
> zero exact agreement. Quote those, not these. Kept because the **method** here — the frozen
> byte-identical prompt, the determinism re-run, the rater-B protocol — is still what is used, and
> because the drop in κ is only interpretable against this baseline.
> Current state: `SESSION_CHECKPOINT.md` and `docs/eval-framework.md` §4a.

**The question.** Every judge number Centri has reported came from a single rater, `Qwen3.6-35B`.
A single rater cannot be checked: the Cohen's κ column of the results table had to be a dash, and
an absolute score like "4.12 of 5" had nothing to be measured against. This is the record of
adding a **second, independent judge** and of what that measurement returned.

**The short answer.** The two judges **agree on the ordering of the tiers and disagree on the
score.** Overall κ = 0.34 (quadratic-weighted), 0.08 unweighted. The tier claim survives an
independent rater; no absolute figure does. On the one criterion a physics worksheet most needs —
whether the numbers hold up — the two raters have **no agreement at all** (κ = −0.04).

Companion docs: `eval-framework.md` (the method this instantiates), `eval-rubric-ika.md` (the
rubric, single source of truth), `eval-progress.md` (dated log).

---

## 1. Design

| | |
|---|---|
| **Unit** | one worksheet (a tiered passage), 21 of them = 7 clips × 3 levels |
| **Instrument** | 12 criteria in 3 axes, each 1–5, plus an achieved-Bloom label — unchanged from `run_llm_judge.py` |
| **Rater A** | `Qwen3.6-35B`, local endpoint, temperature 0, one pass — the run of 2026-07-29 |
| **Rater B** | `Claude Opus 5`, seven independent agents, one per clip, one pass — run 2026-07-31 |
| **Paired ratings** | 21 × 12 = **252** |

**Exact provenance of each rater** — record this, because "an LLM judged it" is not a reproducible
statement and model families move underneath a name:

| | Rater A | Rater B |
|---|---|---|
| Family / tier | Qwen, 35B | Claude, **Opus** (not Sonnet or Haiku) |
| Version | Qwen3.6-35B | **Claude Opus 5** |
| Model ID | `Qwen3.6-35B` (`PI_JUDGE_MODEL`) | `claude-opus-5` |
| Served by | local lab endpoint, `192.168.1.205:8083`, OpenAI-compatible `/v1/chat/completions` | Anthropic, via Claude Code sub-agents |
| Sampling | `temperature 0`, thinking disabled | agent default; not user-settable per call |
| **Scored on** | **2026-07-29** (reported run); re-run as the control **2026-07-31** | **2026-07-31** |
| Also wrote the material? | **yes** — same model family as the generator | no |

**Rater B was run blind.** Each agent was given only the three prompt files for its own clip and
instructed not to open any other file in the repository — no existing judge report, no evaluation
output, no deck, no memo, no source. Seven agents rather than one also means no agent saw more
than three worksheets, so it could not calibrate its scale across the corpus the way a single
pass over 21 would.

### 1.1 The frozen prompt — the part worth reusing

Both raters were sent the **byte-identical question**. The prompt is built once and written to a
file, then replayed verbatim to each rater:

```
tools/export_judge_prompts.py   # build once: one JSON per worksheet, holding the exact
                                # {system, user} strings run_llm_judge would have sent
tools/run_judge_from_prompts.py # replay: --model NAME hits the inference endpoint,
                                # --from-json DIR ingests scores produced elsewhere
```

`run_llm_judge.build_prompt()` is now the single place a judge prompt is assembled; `judge_one()`
calls it. Nothing else may construct one.

**Why this is not ceremony.** If two raters are handed two separately assembled prompts, a
difference in their scores cannot be attributed to the judgement — it could be a difference in the
question. Every comparison in this document depends on that being impossible by construction.

A concrete instance of the risk: the exact flags of the 07-29 run were never recorded, so it was
not known whether it had been given the seed values (`--seed`) or the measured element-interactivity
(`--difficulty-report`). Rather than guess, the local judge was **re-run on the frozen prompts** —
see §4, which settles it.

### 1.2 Where the outputs live

```
material_work/_eval/judge_2026-07-29/          rater A, the reported run
material_work/_eval/judge_claude_2026-07-31/   rater B
material_work/_eval/judge_qwen_2026-07-31/     rater A, re-run on frozen prompts (the control)
material_work/_eval/judge_agreement_2026-07-31.{md,json}
material_work/_eval/pmagic_tables.{md,tex}     the two-rater results table
```

All three judge directories share one format (`judge_<clip>.md`), so any pair can be compared with
`tools/judge_agreement.py --a DIR --b DIR` and any one of them can drive the results table.

---

## 2. Results

### 2.1 Overall and per level

| Set | pairs | Qwen | Claude | gap | exact | ±1 | κ (quad) | κ (unw) | r |
|---|---|---|---|---|---|---|---|---|---|
| **All 12 criteria** | 252 | 4.12 | 3.62 | **−0.51** | 33% | 88% | **0.34** | 0.08 | 0.42 |
| basic | 84 | 3.99 | 3.45 | −0.54 | 31% | 87% | 0.37 | 0.07 | 0.46 |
| intermediate | 84 | 3.92 | 3.43 | −0.49 | 33% | 92% | 0.27 | 0.04 | 0.33 |
| advanced | 84 | 4.46 | 3.96 | −0.50 | 36% | 85% | 0.23 | 0.10 | 0.28 |

**The gap is a near-constant offset.** −0.54 / −0.49 / −0.50 across three levels reads as a
different calibration of the same scale, not a different reading of the worksheets. Claude is
simply the harsher marker.

**The ladder survives both raters.** Both put advanced clearly top and both separate it from the
two lower levels, which sit within 0.07 of each other. Every conclusion Centri draws from the
judge is a *ranking* conclusion, and rankings are what reproduced.

### 2.2 Per criterion

| Criterion | Qwen | Claude | Δ | exact | ±1 | κ (quad) | κ (unw) | r |
|---|---|---|---|---|---|---|---|---|
| motivating_context | 3.76 | 3.05 | −0.71 | 29% | 100% | 0.03 | 0.03 | 0.12 |
| language_clarity | 4.43 | 3.90 | −0.52 | 48% | 100% | 0.13 | −0.08 | 0.28 |
| **cognitive_demand** | 3.81 | 3.14 | −0.67 | 38% | 95% | **0.59** | 0.15 | **0.78** |
| fluency | 4.48 | 3.43 | −1.05 | 14% | 81% | 0.20 | −0.07 | 0.54 |
| completeness | 4.14 | 3.95 | −0.19 | 52% | 100% | 0.45 | 0.20 | 0.49 |
| comprehension | 4.57 | 3.67 | −0.90 | 19% | 90% | 0.15 | −0.13 | 0.41 |
| structure_clarity | 4.57 | 3.57 | −1.00 | 19% | 81% | 0.07 | −0.07 | 0.22 |
| concept_accuracy | 3.57 | 3.29 | −0.29 | 14% | 81% | 0.15 | −0.17 | 0.17 |
| realistic | 3.90 | 3.62 | −0.29 | 24% | 90% | 0.36 | −0.03 | 0.47 |
| variable_name_consistency | 4.67 | 4.14 | −0.52 | 62% | 86% | 0.45 | 0.34 | 0.58 |
| difficulty_fit | 4.48 | 4.48 | **+0.00** | 67% | 95% | 0.31 | 0.40 | 0.32 |
| **grounding_accuracy** | 3.10 | 3.14 | +0.05 | 14% | **52%** | **−0.04** | 0.02 | **−0.05** |

Two rows carry the story.

**`cognitive_demand` is the most legible criterion** (κ 0.59, r 0.78) — and it is the one the tier
claim rests on. It rises for both raters (2.86 → 3.86 → 4.71 for Qwen; 2.43 → 2.86 → 4.14 for
Claude). The criterion doing the most work is the criterion two unrelated models most agree about.

**`grounding_accuracy` has no agreement whatever** (κ −0.04, r −0.05). The two land within one
point on only **52%** of worksheets against 88% overall, and split by a full three points in five
places **in both directions**. Note that the *means* are nearly identical (3.10 vs 3.14) — a
mean-only comparison would have shown perfect agreement on the criterion where there is none.
This is the argument for reporting κ rather than a difference of means.

### 2.3 The case that settles why one judge is not enough

`turntable-3`'s worksheets teach an inward pull of 7.45 m/s², which is a **tracker artifact** —
the jump-free figure is 5.85 (`tracking-data-quality-2026-07-15.md` and the 07-31 jump sweep). The
same wrong number appears in that clip's intermediate *and* advanced worksheet.

| `turntable-3` | Qwen grounding | Claude grounding |
|---|---|---|
| basic | 5 | 4 |
| intermediate | **2** — flagged | **2** — flagged |
| advanced | **5** — full marks | **2** — flagged |

Both judges catch it at intermediate. At advanced, one gives the passage **full marks for
grounding** and the other gives it 2. **The single worksheet in the corpus whose numbers are known
to be wrong was rated perfectly grounded by one rater and badly grounded by the other**, and a
single-rater report would have printed whichever it happened to draw.

Claude's stated reason is arithmetic that does not close: ω²r = 5.82 against a printed 7.45, and
2π/ω = 1.18 s against a printed 1.469 s.

### 2.4 Why grounding disagreement is partly legitimate

Some of it is a real ambiguity in the criterion, not rater noise. The seed values for several
clips **do not satisfy the relations the worksheets print**, for a principled reason: `a_c` is a
mean of instantaneous squares while ω is a mean, and the mean of squares is not the square of the
mean. So a worksheet can faithfully report both measured averages and still print a relation that
does not close.

One rater penalises the passage for asserting a relation that fails on the numbers beside it. The
other accepts it as a faithful report of what was measured. **Both readings are defensible**,
which is exactly why a single number from a single judge should not be quoted as a quality score —
and why `grounding_accuracy` needs to be split, or its wording tightened, before the teacher panel
scores it (§6).

---

## 3. What this licenses, and what it forbids

**Licensed — ranking claims.** "Advanced is more cognitively demanding than basic" reproduces
across two unrelated model families. This is the claim Centri actually makes about tiers.

**Forbidden — level claims.** "4.12 of 5", and its ×2 rescaling to "8.2 of 10" for comparison with
P-MAGIC's 8.2–8.6 band, are properties of the rater as much as of the material. Rater B would have
given 3.62 → 7.2, outside the band. The rescaling already carried a caveat (a linear stretch
cannot equate two instruments); this adds a second, larger one.

**Forbidden — treating κ = 0.34 as a rubric-quality verdict for humans.** This is model-vs-model
agreement. P-MAGIC's 0.76 is between *people*. Two models agreeing would show the rubric is legible
to a machine, not that its scores mean anything about teaching. **The human column is still
empty and this does not fill it.**

---

## 4. The determinism control

Re-running rater A on the frozen prompts, two days after the original run:

| | |
|---|---|
| worksheets | 21 of 21 |
| paired ratings | 252 |
| identical | **252 (100%)** — zero differences |
| κ | **1.00** |

**The local judge is deterministic.** Two consequences:

1. **The judge-to-judge gap is a rater difference, not run-to-run noise.** This is ruled out by
   measurement rather than assumed.
2. **The 07-29 run had been given the same prompt this comparison uses.** Reproducing it exactly
   from the frozen prompt is only possible if the original prompt matched — which retroactively
   settles the unrecorded-flags problem from §1.1.

**The comparison is invariant to which rater-A run is used.** Recomputing agreement against the
07-31 re-run instead of the 07-29 original gives the *same* κ = 0.34 / 0.08
(`judge_agreement_matched_2026-07-31.md`) — necessarily, since the two runs are bit-identical, but
it is worth having on record that the headline number does not depend on that choice.

**Contrast the writer, which does not reproduce.** Regenerating the same worksheets moved the
deterministic checker from 19/21 to 16/21. **The model that grades is stable; the model that
writes is not.** So a single-run judge number may be quoted with the run named; a single-run
*generation* number may not, and needs a mean across runs.

Cost: ~20 minutes for 21 worksheets against the lab endpoint.

---

## 5. Computing κ — two traps, both hit

Both were caught before reaching a slide; both are now pinned in
`tools/tests/test_judge_agreement.py` (7 tests).

**Trap 1 — a scale error that inflates κ by a factor of n.** The expected-disagreement term takes a
single `1/n²` (the two marginals carry one `n` each). An extra `÷n` makes κ grow with the number of
pairs: at n = 252 it would have reported a number far above 1.0, and at smaller n a plausible-looking
one. Verified against the textbook 2×2 (both-yes 20, both-no 15, splits 5 and 10 → κ = 0.40), and
pinned by a test asserting κ is unchanged when the same data is tripled.

**Trap 2 — zero variance is undefined, not zero.** If both raters score a criterion 5 every time
(`variable_name_consistency` at advanced does exactly this), chance agreement is 1.0 and κ is 0/0.
Returning 0.0 would print as "no agreement" — **the precise opposite of what happened**. It is
reported `n/d`.

**Weighting.** κ is reported **quadratic-weighted** by default: on an ordinal 1–5 scale, 4-against-5
is a near miss and must not count the same as 1-against-5. The unweighted value is carried alongside
because it is the stricter reading, and the gap between them (0.34 vs 0.08) is informative — the
raters are usually close but rarely identical.

---

## 6. Threats to validity, and what is not yet known

- **Rater B is one model, run once.** Seven agents give independence *across clips*, not repeated
  measurement. Rater B's own test-retest was not measured; only rater A's determinism was.
- **Rater A wrote the material.** `Qwen3.6-35B` grades its own output. Rater B does not, which is
  the main thing the second judge buys beyond a κ. It does not establish which rater is *right*.
- **n = 21 is small for a per-criterion κ.** Each criterion's κ rests on 21 paired ratings; the
  per-criterion values in §2.2 should be read as indicative, the overall 252-pair figure as solid.
- **Neither judge is validated against a human.** ICC(2,k) against the teacher panel is the
  measurement that would make either judge trustworthy at scale, and it does not exist yet.
- **`grounding_accuracy` may be underspecified rather than merely hard.** §2.4 suggests the
  criterion silently asks two questions — "do the numbers trace to the measurement?" and "do the
  relations printed beside them close?" — which the deterministic checker separates and the rubric
  does not. Splitting it is a candidate fix, and must happen *before* the teacher panel scores it,
  or the human κ will inherit the same ambiguity.

---

## 7. Reproducing this

```bash
cd agent-backend

# 1. freeze the question, once, for all 21 worksheets
python3 tools/export_judge_prompts.py --workspaces 'workspaces/job_*' --out /tmp/judge_prompts

# 2a. rater A — the local endpoint
python3 tools/run_judge_from_prompts.py --prompts /tmp/judge_prompts \
    --out material_work/_eval/judge_qwen_<date> --model Qwen3.6-35B

# 2b. rater B — agents, one per clip, blind; then ingest their JSON
python3 tools/run_judge_from_prompts.py --prompts /tmp/judge_prompts \
    --out material_work/_eval/judge_claude_<date> --from-json /tmp/judge_claude \
    --label 'Claude Opus 5'

# 3. agreement
python3 tools/judge_agreement.py \
    --a material_work/_eval/judge_2026-07-29    --a-label 'Qwen3.6-35B' \
    --b material_work/_eval/judge_claude_<date> --b-label 'Claude Opus 5' \
    --out material_work/_eval/judge_agreement_<date>.md

# 4. the two-rater results table (P-MAGIC Table 7 shape, kappa column filled)
.venv-eval/bin/python tools/build_pmagic_tables.py \
    --judge-dir material_work/_eval/judge_2026-07-29 \
    --judge-dir-b material_work/_eval/judge_claude_<date> \
    --judge-label 'Qwen 35B' --judge-label-b 'Claude' \
    --ref material_work/_reference/openstax_6.2/reference.json \
    --materials '<staged>/*.json' \
    --out-md material_work/_eval/pmagic_tables.md --out-tex ../presentation/pmagic_tables.tex
```

**Staging gotcha for step 4.** `--materials` keys each text by its filename stem, and every clip's
worksheet is called `material.basic.json` — so globbing the workspaces directly collapses 21
worksheets into 3. Stage them under unique names first (`<clip>__<tier>.json`). The auto table is
correct when it shows n = 7 per level and n = 21 total; if it shows n = 0 per level, the stems
collided.

---

## 8. Bottom line

Adding a second judge did not raise a score. It **bounded the meaning of every score already
reported**: the tier ordering is reproducible across raters and is the claim to make; the absolute
level is not, and is a property of the rater. It also produced the sharpest available argument for
the teacher panel — on the one worksheet whose numbers are known wrong, two competent readers of
the same rubric split 5 against 2.
