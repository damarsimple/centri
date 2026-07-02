# Writing detection prompts (`visual_cues` / `targets`)

**The single most important knob for tracking reliability is the *wording* of the object
prompt.** Both trackers are open-vocabulary, text-conditioned detectors, so detection is a
**text↔image similarity match** — a common, concrete category noun lands on the object; a
rare descriptive phrase embeds far from it and misses.

## Rule of thumb
> Use the **simplest common category noun** that is unambiguous. 1 word if possible.
> **No color/material/possessive adjectives, no compound descriptions.**

This is the right *default*, but the optimal word is **tracker-specific** — verify on the
production tracker (see "The best wording is TRACKER-SPECIFIC" below). On a hard object,
single nouns can score 0 while a 2-word cue (`"yellow toy"`) scores 100%.

| Good | Bad |
|---|---|
| `toy` | `cream colored doll` |
| `phone` | `red phone lying on the turntable` |
| `wheel`, `fan blade` | `rear bicycle tire with reflectors` |

## Evidence (ceiling-fan-doll clip, 2026-06-21)
Same object, same frames, LocateAnything `/segment`, 20 frames sampled across the clip:

| prompt | hit rate |
|---|---|
| `toy` | **100%** (20/20) |
| `small toy` | 80% |
| `yellow object` | 75% |
| `doll` | 70% |
| `object tied with green string` | 60% |
| `stuffed toy` / `plush toy` / `stuffed animal` | 10% |
| `teddy bear` | 5% |
| `cream colored doll` (original sidecar) | **6%** |

A **16× swing** (6% → 100%) from wording alone. ROI-cropping did **not** help (the object
was clearly visible to a human in the crop but LA still missed it with the bad prompt) —
confirming the bottleneck is *recognition/wording*, not resolution. See
[`test/fan-tracking-findings.md`](../../test/fan-tracking-findings.md) and the
`test/fan_la_*_montage.jpg` images.

## Why both trackers suffer (mechanism)
- **Production tracker = SAM3-CPP (GGML).** It is served by
  `/home/damar/sams2/sam3cpp/api_master_sam3.py` at `10.0.0.1:8086` (supervisor `run_sam3.sh`,
  conda env `sam3`), which shells out to a **C++ binary + GGML models** (`sam3-q4_0.ggml`,
  `sam2.1_hiera_large_f16.ggml`). It grounds the text query natively and SAM2 propagates.
  > **Correction (2026-06-21):** the older claim that "SAM3 grounds via YOLO-World
  > (`ultralytics.YOLOWorld`, `sam3/worker_segmenter.py`)" is **stale** — `worker_segmenter.py`
  > is an unused alternate path, not what `:8086` runs. Proof: a 12-frame YOLO-World sweep
  > scores `"fan blade"`=0/12, but production `/track` scores `"fan blade"`=100% → different model.
- **LocateAnything path**: a VLM grounding model (Qwen2.5-3B + MoonViT) that predicts boxes
  for a text query.
- Both embed the **query text** and match it to image regions. Rare/over-specified phrases
  (`"cream colored doll"`) sit in a sparse region of the text embedding space and match
  poorly; concrete category nouns match strongly. This is why the *same footage* goes from
  untrackable to 100% just by changing the word.

## The best wording is TRACKER-SPECIFIC (2026-06-21)
The "simplest noun" rule is the right default, but the *winning* word differs per model — so a
sweep on the **actual production tracker** beats trusting a sweep done on a different one.
Evidence — ceiling-fan doll, 72-frame `/track` sweep on production **SAM3-CPP** vs the LA
`/segment` sweep above:

| prompt | LocateAnything `/segment` | production SAM3-CPP `/track` |
|---|---|---|
| `toy` | **100%** | **0%** |
| `doll` / `ball` / `ornament` / `small toy` | mixed (≤70%) | **0%** |
| `yellow toy` / `hanging toy` | — | **100%** (tracks the orbiting doll) |
| `fan blade` | — | 100% (but centroid ≈ hub → no usable orbit) |

Takeaways: (1) LA liked single `"toy"`; SAM3-CPP needed the **two-word** cue. (2) Track the
*orbiting* object, not the big easy one — `"fan blade"` covers 100% yet yields no rotation.
(3) Practice: micro-sweep a few candidate cues on the live tracker before committing a sidecar.
Sweep scripts: `/tmp/fan_sweep/{track_sweep.py (live /track), viz.py, sweep.py (YOLO-World)}`.

## When prompt wording is NOT enough — switch tracking mode (2026-06-25)
Some scenes defeat *any* prompt for an appearance tracker, and the fix is the **mode**, not
the word (see [data-contract.md §1a](data-contract.md)):
- **Identical repeated shapes** — 5 identical fan blades. SAM3 can't tell them apart and
  hops between them; at speed net rotation reads ≈0 (wagon-wheel aliasing). Even `"fan blade"`
  at 100% coverage gives a jittering ω. → mark one blade and use `tracking_mode:"color"`
  (follows the *right* one by hue; SAM3 is colour-blind so the marker can't help *it*).
- **Under-sampled rotor (the real fix is fps, not the mode)** — a fast identical-blade rotor
  shot at **30 fps** wagon-wheels: blades advance more than ~½ a blade-pitch per frame, so the
  shape-tracker hops blade-to-blade and net rotation reads ≈0. ⇒ **shoot at 60 fps first** —
  on `IMG_3750.MOV` SAM3 `"fan blade"` at 60 fps tracked the 10–20 s peak window at 100 %
  coverage, ω≈4.15 rad/s, *clean* (the orange marker is **sharp**, ~120×124 px, at peak — this
  was under-sampling, **not** motion blur). Only drop to `tracking_mode:"frequency"` when even
  60 fps under-samples (blade-pass approaching `fps/2`) or you need ω(t) without a per-frame
  point: blade-pass FFT on a ring → ω, no point-tracking. (On the same peak window the ring-FFT
  gave 2.70 Hz blade-pass → ω=3.39 rad/s, all 12 probes within 0.03 Hz — a valid cross-check,
  but object mode at 60 fps is the simpler primary path here.)

## Where this applies
- **Sidecar** `tracked_object.visual_cues` and `reference_geometry.label` — these become the
  `/track` `targets`. This is the main lever. (`agent-backend/docs/data-contract.md`)
- **`/suggest-scene`** (the VLM that auto-proposes the object) and the app's **AnnotateScreen**
  — they should emit/encourage **simple category nouns**, not descriptive phrases.
- **`/verify-objects`** — a setup that verifies on frame 0 with a simple noun is far more
  likely to track well across the video.

## Recommended follow-ups (not yet done)
- Update the `/suggest-scene` prompt to return a **single common noun** per object (strip
  adjectives), and add an AnnotateScreen hint ("use one simple word, e.g. *toy*, *wheel*").
- Optional: a built-in **prompt micro-sweep** — before a full `/track`, probe a few candidate
  nouns on ~10 sampled frames via `/segment` and pick the highest hit-rate cue automatically.

## Reproduce the sweep
```python
# LA worker on :8087, frames in /tmp/faniml
for p in ["toy","doll","cream colored doll","small toy","stuffed toy"]:
    # POST /segment with targets=[p] over N sampled frames, count objects[p] is not None
```
(See the session log / `test/fan-tracking-findings.md` for the exact script.)
