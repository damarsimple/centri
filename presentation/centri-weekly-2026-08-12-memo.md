# Centri — weekly memo, week ending 2026-08-12

Companion to `centri-weekly-2026-08-12.pdf`. The deck is sparse by design; this memo carries the
definitions, the caveats and the reasoning, and is written to be read without the presenter.
Every claim in the deck appears here.

---

## 0. What Centri is, in one paragraph

Centri takes an ordinary phone video of something going round in a circle — a ceiling fan, a
playground roundabout, a phone spinning on a turntable — measures the motion from the pixels, and
writes physics worksheets from those measurements at three difficulty levels. The point is that
the numbers in the worksheet are the student's *own* video, not a textbook's invented example.
The sibling system in the same lab, **P-MAGIC**, does the same thing from a phone's motion
sensors rather than from video; the parent line is the **Utami dissertation**, from which the
scoring rubric is adopted so the two sets of numbers can be compared.

**The state of the work:** the measurement and the writing both work end to end. What has never
been established is whether anybody *learns* from the result. That still requires teachers.

---

## 1. The headline: the corpus changed, and every number was re-derived

Three of the seven clips left the corpus this week and one entered it. **The corpus is now five
clips and fifteen worksheets** (five clips × three levels), down from seven and twenty-one.

### 1.1 The two ceiling fans were re-shot

The old fan clips were measured in a mode called **frequency tracking**: a fan's blades are
identical and motion-blurred, so no single point on the fan can be followed from frame to frame.
Instead the software watched the brightness at one spot flicker as blades passed, worked out the
rotation *rate* from the flicker frequency, and then **drew a circular path from that rate**.

The rate was real. The path was not — it was constructed from the rate and then annotated onto
the video frame as though it had been observed. Six worksheets were built on it.

**The fix was a piece of yellow card taped along one blade.** With something on the fan that is
actually distinguishable, ordinary colour tracking follows it directly:

| | old fan clips | re-shot clip (`fan-4656`) |
|---|---|---|
| what is measured | a rate | **a trajectory, every frame** |
| the orbit drawn on the frame | invented from the rate | **observed** |
| coverage | — | 99.99% of 13,781 frames |
| revolutions tracked | — | 190.8 |
| detections off the orbit | — | **zero** |
| comes to rest on camera | no | **yes** |

The marker is about a thousand times larger than the next yellow-ish thing inside the fan's
radius, so finding it needs no machine-learning detector at all.

Three of the four takes filmed were rejected on measurement rather than taste: one is 2.7 seconds
of somebody's face; one was handheld in portrait with wooden ceiling louvres that fall in the same
colour band as the card, giving only 37% of detections on the orbit; one occasionally jumps to a
wooden window frame. The fourth is the one now in the corpus.

### 1.2 `turntable-3` was withdrawn

The marker on this clip normally moves **1.4 pixels** between frames. Three times it moves
**604, 614 and 713 pixels in a single frame**, flipping between two positions about 728 pixels
apart. One of those jumps falls inside the window the physics is measured over.

The pipeline smooths its data over 21 frames, which spreads each jump into a symmetric ramp about
12 frames wide — which is why they appear in the graphs as smooth "mountains" rather than as
obvious steps, and why the rotation rate appears to climb from 0 to 10.2 rad/s during an interval
in which the tracked position does not actually move.

**Effect: the worksheets taught an inward acceleration of 7.45 m/s². Without the bad frames it is
5.85 — the published figure was 27% too high.** The clip was withdrawn rather than repaired,
because two further problems on the same clip were never separated from this one (see §7).

### 1.3 Nothing was deleted

Both fan templates, the turntable template, and all three job workspaces are archived with a
written record of the evidence that condemned them. This is standing project policy: a clip that
cannot be trusted is parked with its diagnosis, not removed, so the reasoning survives.

**Consequence for every number previously reported:** the gate score, both judges' means, the
agreement statistic, the BERTScore figures, the diversity figures, the difficulty ladder and the
readability numbers all described a corpus that no longer exists. All were **re-derived from
scratch**. None was rescaled or adjusted.

---

## 2. Checking the rotation rate without a sensor

The strongest measurement result this week. The re-shot fan's rotation rate was measured a second
time by a **completely independent route**: take the brightness of a single 12×12-pixel patch of
the image, watch it flicker as the five blades pass, Fourier-transform that signal, and divide the
dominant frequency by five. **This uses no marker and no tracker** — it shares no code and no
assumption with the primary measurement.

| Window | marker track (rad/s) | blade-pass (rad/s) | difference |
|---|---|---|---|
| 78–90 s | 6.199 | 6.190 | **+0.16%** |
| 112–124 s | 6.172 | 6.170 | **+0.03%** |
| 146–158 s | 5.046 | 4.997 | +0.99% |
| 180–192 s | 1.331 | 1.335 | −0.34% |
| **214–226 s (fan at rest)** | **0.016** | **4.690** | *see below* |

Two unrelated principles agreeing to under 1% on every steady window.

**The last row is the point.** The fan is stopped. The marker track correctly says so. The
blade-pass method reports 4.69 rad/s anyway — it is reading noise as if it were rotation. That is
the defect that made the old fan clips unsafe, measured directly, on the same frames, against a
method that gets it right. It could not have been demonstrated without a clip that comes to rest
while the camera is still running.

**Important limitation: this is not a sensor check.** Both measurements come from the same video.
What this establishes is that the marker-tracking step introduces no rate error. It is a narrower
claim than comparing against a physical instrument, and it is reported as one.

---

## 3. The metre scale: the card is its own ruler

To convert pixels into metres the software needs one distance it knows in both units. A ruler is
useless here — at ceiling distance its markings do not resolve. It turned out not to be needed.

Three tape measurements were taken: hub to the card's near edge **31 cm**, the card itself
**25 × 18.5 cm**, hub to blade tip **≈51 cm**. Initially these disagreed with the pixel
measurements by up to 38%. Two observations resolved it, both confirmed against the footage:

1. **The card lies along the blade**, its long axis only 4.2° off the radial direction (measured
   over 166 frames). So its 25 cm runs *outward*: the card covers a span, not a point.
2. **The card's outer edge is the blade tip.** Predicted position 329.5 px; the blade-tip circle
   measured independently from 800 tip points sits at 319.3 px — agreeing to 3.2%.

So the card occupies the outer 25 cm of the blade: near edge at 31 cm, **centre at about 44 cm**,
far edge at the tip.

| span | tape | pixels | implied scale |
|---|---|---|---|
| hub to card's near edge | 31 cm | 190.5 px | 615 px/m |
| card length | 25 cm | 139.0 px | 556 px/m |
| **both, fitted together** | | | **591 px/m** |

The tracked point is the card's *centre*, at 44 cm — and the pipeline now reports a fitted radius
of **0.4400 m**, matching the tape exactly.

**This caught a 40% calibration error before a single worksheet was generated.** The first
configuration read the 31 cm as the distance to the card's *centre* when it is the distance to its
*near edge*. That gives 839 px/m instead of 591 — which would have made every distance, speed and
acceleration in the material **29% too small**. The general lesson: *"distance to the marker" is
ambiguous the moment the marker is bigger than a point*, and the two spans that form the scale
must describe the same thing.

**Honest bound: the scale is good to about ±5%** (556–615 px/m from its two anchors). Rotation
rate, period and frequency do not depend on it at all and are good to under 1%.

---

## 4. Two defects found in our own software

### 4.1 A correction step that measured the tilt and then ignored it

The fan is filmed from about 34.5° off square, so its circular orbit appears in the image as an
ellipse. The software has a correction for exactly this. It did not run.

The reason is a mismatch between what the check asks and what the problem is. The check asks
whether the fan's centre appears *offset* from the middle of the ellipse — which happens when the
camera is close and the perspective converges. On this clip the centre is essentially dead-on
(0.05 px), so the check concluded there was nothing to do. But the code had already measured the
ellipse's shape two lines earlier and discarded that measurement.

**The cost was not just a distorted graph. It was an ambiguity.** A tilted orbit has three
plausible "radii" — the long axis (260 px), the short axis (214 px), and a compromise circle
(245 px) — and nothing chose between them. Two runs of the **same video with the same settings**
picked differently, giving scales of 591 and 558 px/m and a **6% difference in the taught
acceleration**.

The fix straightens the ellipse first, using only the ellipse's own geometry. Afterwards exactly
one radius exists and the ambiguity is gone. Out-of-roundness falls from 7.29% to 3.41%.

**This affects exactly one clip.** The roundabout has genuine perspective and keeps the older,
stronger correction; one turntable clip is already round enough to leave alone; another has no
centre mark. That was verified, not assumed.

**A claim in the technical report is retracted as a result.** It said that a tilted-but-centred
view "needs no un-projection". That is false: a uniformly spinning circle seen at a tilt has an
apparent rotation rate that swings by ±19.6% at this angle. The claim survived because every clip
the report was written about is round to within 3.5%, where the error is smaller than the noise.
The re-shot fan is the first clip tilted enough for it to matter.

### 4.2 A tracker that could not let go

The colour tracker refuses candidate positions that are too far from where it last saw the
marker — a sensible rule that stops it jumping to a similarly-coloured blade. The flaw was in what
happened when *nothing* qualified: the frame was recorded as a miss, but the tracker kept its old
reference position. So a single bad frame — a blur, a brief occlusion, a genuine speed-up —
stranded it, and it could only recover when the marker orbited back to near where it had been
frozen: **once per revolution**.

| clip | coverage before | coverage after |
|---|---|---|
| `fan-4656`, with the setting that exposed it | 26.9% | **92.6%** |
| `computerfan-4029` | 86.9% | **99.3%** |

The second row matters most: `computerfan-4029` is a corpus clip that had been **scored, reported
and taught from** at 86.9% coverage, and nothing flagged it, because a tracker discarding frames
looks exactly like an object that is hard to see. Recovering its 102 lost frames moved its taught
acceleration by **21%**.

The fix drops a reference position that has explained nothing for five consecutive frames. On
every frame the old code handled, the new code returns the **identical** position — the change can
only add data, never alter it. The tracker now also reports how often it had to re-acquire, which
is the diagnostic that was missing.

---

## 5. What the phone's gyroscope actually showed

One clip — the withdrawn `turntable-3` — was filmed while the phone logged its own gyroscope,
giving an independent physical measurement of rotation rate. This is the project's only
sensor-based check, and it was being read incorrectly.

| peak rotation rate | rad/s | vs sensor |
|---|---|---|
| as shipped | 12.348 | **+25.5%** |
| **same run, three bad frames removed** | 9.431 | **−4.1%** |
| a second run of the same video | 9.781 | −0.6% |
| **the gyroscope** | **9.838** | — |

The two runs differ in several ways, and the difference had been attributed to the perspective
correction. **It is not that.** Three frames out of 350 account for almost the entire error;
the correction and everything else account for the last few percent. The two effects had been
confounded because the second run happens to have no bad frames at all.

**The phone's own sensor caught the teleports weeks before anyone went looking for them.** Nothing
else in the stack can: a deterministic checker verifies that numbers trace back to the
measurement, and three bad frames trace perfectly well.

---

## 6. Evaluation results on the new corpus

Four independent layers score the material. All were re-run on the fifteen new worksheets.

### 6.1 Similarity to a textbook (automatic)

BERTScore F1 against the OpenStax section on circular motion: **0.799 / 0.824 / 0.828** for
basic / intermediate / advanced, 0.817 overall. Spread *within* a level is ±0.003; across all
fifteen worksheets ±0.013.

**These metrics read the difficulty level, not the video.** Almost all the variation is between
levels rather than between clips. They are reported only so the numbers line up with P-MAGIC's
published table; a higher score means "more like the textbook", not "teaches better".

### 6.2 The rubric

Twelve criteria, each scored 1–5. Ten are adopted from the parent dissertation so the rows match
theirs; two are Centri's own. **The same instrument goes to the teacher panel unchanged** — only
the rater differs.

Two raters scored all fifteen worksheets: the local **Qwen3.6-35B** model, and **Claude Opus 5**.
Both were sent a **byte-identical** prompt, frozen once and replayed, so any difference between
them is a difference of judgement rather than of wording.

Overall means, all twelve criteria: **3.57 / 3.83 / 4.58** (Qwen) and **3.72 / 3.72 / 4.18**
(Claude).

### 6.3 The difficulty claim

**Cognitive demand rises for both raters** — 2.80 → 3.60 → 4.80 and 3.00 → 3.20 → 4.20 — and it
is the criterion the two raters agree on best (κ = 0.70, correlation 0.80). *This is the
difficulty result.*

There is a second measure, "element interactivity", which counts how many distinct quantities and
relationships a passage juggles. It rises 5 → 22 → 37 across the levels on every clip. **It is
not evidence.** The generator is *required* to produce a rising ladder and re-rolls a level until
it does, so a rising ladder demonstrates that the generator met its specification. It is reported
as a conformance check.

Reading grade does **not** rise reliably (2 of 5 clips), and is reported rather than optimised.

### 6.4 Where the raters disagree, and why it matters

Overall agreement is **κ = 0.31** (quadratic-weighted; 0.14 unweighted) over 180 rating pairs.
The raters agree on the *ordering* — both put advanced top — and not on the score.

| criterion | κ | exact agreement | within 1 point |
|---|---|---|---|
| cognitive demand | **0.70** | 60% | 100% |
| completeness | 0.58 | 53% | 100% |
| variable naming | 0.51 | 60% | 93% |
| **grounding accuracy** | **−0.07** | **0%** | **33%** |

**Grounding accuracy has zero exact agreement across fifteen worksheets.** The criterion silently
asks two different questions — *do the numbers come from the measurement?* and *does the
arithmetic printed beside them actually work?* — and the two raters answer different ones. It must
be split before it goes to teachers, or the human agreement figure will inherit the same
ambiguity.

With n = 15 these per-criterion figures are **indicative, not precise**: the confidence interval
on any one of them is wide. The honest reading of the grounding row is "no detectable agreement",
not "−0.07".

### 6.5 Each layer caught something the others could not

| layer | what it caught |
|---|---|
| deterministic gate | ungrounded rate-vs-period wording, in 4 of 15 worksheets |
| LLM judge (Claude) | **an arithmetic error the gate passed** (below) |
| phone gyroscope | the three teleports — 25.5% on peak rate |
| an independent measurement principle | the old fan method reporting 4.69 rad/s at rest |
| **none of them** | **an overlay drawn 328 px off its object** (§6.6) |

The judge's catch is the interesting one. On `turntable-2` the intermediate worksheet walks the
reader through the calculation ω² × r and prints the answer as **4.91 m/s²**. The correct product
is 4.83² × 0.185 = **4.31**. The passage then asserts the result agrees with the measured average.

**The deterministic gate passed this worksheet**, and was right to by its own standard: 4.91 *is*
the measured average acceleration and traces correctly to the measurement. The two simply are not
the same quantity — the average of ω²r is not ω²r computed from the average ω, because ω varies
(a 13.7% gap here). The gate can check that a number traces; it cannot check that a relation
printed beside it closes.

**Tracing a number is not validating it.** That is the project's governing lesson, and it applies
to our own instrument as much as to the generated text.

---

### 6.6 The defect no layer caught

On the computer-fan clip, every drawing laid over the video frame was positioned **328 pixels too
low**. The green cross marking "the centre of rotation" sat on a fan blade rather than the hub, and
the circle showing the marker's path ran off the fan and onto the desk below. This was not only in
a debug view: the same drawing is embedded in all three of that clip's student worksheets, so a
learner would have been shown an inward pull pointing at a table.

**None of the four checking layers reported it.** It was found by opening the annotated video and
looking at it.

To explain why, two terms. The system trims each video down to a smaller rectangle around the
moving object before analysing it — call that the *crop*. Positions can therefore be expressed
either in the original full frame or inside the crop, and the two differ by a fixed offset, here
328 pixels vertically. The tracked path had been recorded in full-frame terms while being drawn
onto the cropped picture.

The reason nothing caught it is that **the path and the centre point were displaced by the same
amount, in the same direction.** Every quantity that depends on their *relative* position was
therefore still correct: the orbit radius agrees to within 0.5% with a measurement made directly
against the video, and the rotation rate is unchanged to thirteen digits. No taught number was
wrong. The gate checks that printed numbers trace back to the measurement, and they did. The
figure checker was written for exactly this kind of error, but it compares each drawing against
the recorded path — which was in the same displaced frame, so it compared the mistake against
itself and passed. The two independent raters had scored an earlier run of the same clip that
happened to be positioned correctly.

**A frame of reference cannot be audited from inside itself**, and all four layers were inside it.

The repair appeals to something outside the data. A path measured inside the cropped picture
cannot contain a point that lies outside that picture — the file simply does not extend that far.
So any point beyond the crop's edge proves which frame the path is in, without consulting the
centre, the radius, or any other fitted value. Here the path reached 1384 pixels down a picture
only 1244 pixels tall. The system now applies that test first and lets the older, weaker test
decide only when the path fits entirely inside the crop and therefore proves nothing.

Two consequences worth stating plainly. First, this bounds what the table in §6.5 is evidence
for: layers catch errors visible in the quantity each layer inspects, and this error was
consistent in every quantity and wrong only against the world. Second, the strongest row in our
whole evaluation — the one rating whether annotations are correct — was scored on the correctly
positioned earlier run, so it is **not** evidence that this class of error would be caught. A
deliberately mis-positioned overlay should be put in front of the raters before that row is
quoted again.

---

## 7. What is still unproven

| open question | what would settle it |
|---|---|
| **Does anybody learn from it?** | the teacher panel |
| No clip has a sensor cross-check any more | re-shoot one clip logging its gyroscope |
| Grounding accuracy asks two questions | split the criterion, then re-rate |
| The metre scale rests on one clip | a known length in every scene |
| Nothing rejects a teleport automatically | build the guard — the sweep is still by hand |

**Withdrawing `turntable-3` removed the only clip with a paired sensor log.** That is a genuine
cost of the decision. The nearest replacement — the blade-pass cross-check in §2 — is independent
of both the marker and the tracker, but it is derived from video rather than from a physical
instrument, which is a weaker claim.

Two further problems on that clip were never separated from the teleports and now cannot be: the
sensor comparison was run on a *rectified* version of the workspace whose fitted radius differs
from the shipped one by 38%, and the clip shows an unexplained speed-up during a coast-down that
falls outside every contaminated window.

**Everything measured so far is a property of the text and of the measurement.** Whether a student
learns more from a worksheet built on their own video than from a textbook example is the question
the project exists to ask, and no number in this memo answers it.

---

## 8. Reproducing what is here

- Corpus: `agent-backend/workspaces/job_{roundabout-4046, computerfan-4029-2, turntable-1,
  turntable-2, fan4656final}`
- Withdrawn clips: `agent-backend/workspaces-archive/{withdrawn-turntable3-20260806,
  superseded-by-fan4656-20260806}`, each with a README recording the evidence
- Frozen judge prompts: `material_work/_eval/judge_prompts_2026-08-06/` (both raters answered
  these byte-identical files)
- Rater scores: `material_work/_eval/judge_{qwen,claude}_2026-08-06/`
- Agreement report: `material_work/_eval/agreement_2026-08-06.md`
- Tables in the deck: built by `tools/build_pmagic_tables.py` — regenerate, never hand-edit
- Per-clip measurement detail: `technical-report/centri-video-data-quality.pdf`, rev. 2026-08-06
