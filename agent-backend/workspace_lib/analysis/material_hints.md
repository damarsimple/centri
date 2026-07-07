# Material-generation nuances (read as hints)

The tiered-material generator (`material_tiers.py`) loads this file verbatim and injects it
into the system prompt as a NUANCES block, ahead of the JSON-output instruction. These are
**subtle wording hints** distilled from real gate rejections — not new rules. Edit this file
(no code change needed) to teach the model a phrasing without re-touching the prompt template.

**Why this file exists (35B limitation).** The local model (Qwen3.6-35B) is reliable at the
*first* draft but poor at *self-correcting* on regeneration: told "you used a banned word," it
often re-emits the same word or trades it for another violation (e.g. `recorded` → `pushes`).
So the durable fix is to steer the FIRST pass with concrete hints here, rather than leaning on
failure-informed regeneration. Generalizing this away is future work (a stronger model, or a
review-and-select generation loop as in Utami's SocioMathLLM).

## Wording hints

- **"matches the measured value", never "recorded".** When you state that a computed number
  agrees with the ground truth, write "matches the **measured** value / period / acceleration"
  or "agrees with the value from the data". The word *measured* is allowed; *recorded* is not
  (it reads as the video recording). This is the single most common rejection — avoid it.

- **Name figures by what they SHOW.** A plot is "the graph of how the angle grows / how the
  turn-rate changes"; the still image is "the labelled photo" or "the picture of the object on
  its base". Never "the annotated frame", "the recorded frame", or "the captured image".

- **Slowing motion: say it plainly.** For a decelerating clip, write "it slows down / loses
  spin smoothly and comes to rest". Do NOT hedge it as "does not speed up or slow down" — that
  literal phrasing reads as *steady* motion and is a faithfulness error.

- **ω² is a fine intermediate.** Showing "squaring the turn rate ω gives ω² …, then a_c = ω²·r"
  is correct and grounded — quote the ω² value that squares your cited ω.

- **Work your example at the ASSIGNED instant.** When an anchor policy names a specific worked
  instant (e.g. t = 2.72 s), verify your single numeric example at THAT instant, not another —
  each tier is assigned a distinct one so the three passages stay distinct.

- **Basic "angle over time": use ONLY the milestone times you are given.** Narrate the sweep at
  the exact angle-milestone times supplied (e.g. "after 1.0 s … a quarter turn"). Do NOT invent
  in-between times like "in about 0.21 s" or "by 1.7 s" — any time not in the data is ungrounded.

- **No causes.** The speeding-up / slowing-down has no named cause at any tier — never a motor,
  brake, friction, drag, or force. The inward effect is only "centripetal acceleration" (you
  may call it an "inward pull").

- **Fit quality is qualitative — never cite a specific R².** When you note the α (angular-
  acceleration) fit is good, say "the turn-rate falls in an almost perfectly straight line" or
  "an excellent constant-deceleration fit". Do NOT state a numeric R² (e.g. "R² = 0.99976") — the
  pipeline does not report that statistic, so any specific value is ungrounded and fabricated.
