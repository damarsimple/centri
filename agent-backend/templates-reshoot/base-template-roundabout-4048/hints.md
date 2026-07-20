# Processing hints — base-template-roundabout-4048

> Read before Step 2. Clip-specific; takes precedence over your defaults.
> Evidence and numbers: `docs/tracking-data-quality-2026-07-15.md`.

## Verdict: this clip is NOT usable. Do not produce material from it.

**Stop and report `failed` with the reason.** The information needed to track this knob is not
in the pixels. No parameter, no filter, and no smarter model recovers it — the fix is a
re-shoot. Passing a plausible-looking track downstream from this clip is the failure mode to
avoid, not the tracking itself.

**Scene.** A large 8-spoke yellow wheel on a red post, black knobs on the rim, outdoors, spun
by hand for ~1 revolution around t = 23–29 s. Otherwise at rest. Filmed against a park
background of dense dark foliage.

## Why it is unrecoverable

The target's defining feature is *darkness*, and the background is also dark. The knob's orbit
passes straight through the foliage for the top half of every revolution. Inside the rim
annulus alone there are **~33 competing dark blobs per frame** (74,463 across 2,220 frames).
The knob is separable only on the bottom arc, against bright paving.

See `docs/figures/mask-4048-foliage.png` — the HSV "dark" mask, with the rim annulus drawn.
The top of every frame is a solid mass of foliage that the threshold cannot distinguish from
the knob.

Correctly-gated re-tracking gives an **honest 14% coverage**. The cached track claims
`track_coverage: 1.0` and is wrong in ~38% of frames. Coverage is not correctness.

## The two real tracker bugs this clip exposes (they matter elsewhere)

Both are genuine defects worth fixing in `color_track.py` even though they do not save *this*
clip:

**1. `area × mean_saturation` scoring is invalid for a dark target.**
```python
chosen = max(pool, key=lambda c: c[2])   # c[2] = area * mean_saturation
```
Black is defined by low **value**; its saturation is meaningless noise. The score degenerates
to "the biggest dark blob in the ROI" — a tree, a shadow, the whole rig, never the small knob.
The detected bbox ranges 8 px to 658 px wide (area CV **2.08**). For a dark target, score by
agreement with the *predicted position* and the target's *expected size*; never by raw blob
size.

**2. `max_step: 250` when the knob moves 8.3 px/frame — 30× too loose.**
Derive it from physics: `ω·r/fps` = 1.1 × 450 / 60 = 8.3 px/frame, then allow ~3× → **~25**.
The observed p99 step is **240.9 px**: the tracker is using its full allowance to teleport. And
because `prev` then follows the wrong blob, the error is **sticky** — a too-loose `max_step`
does not merely permit errors, it makes them permanent.

Fixing both (annulus gate on the rim + `max_step` 25 + predict-and-match scoring) takes this
clip from 137 jumps over 100 px to **zero**, and bbox area CV 2.08 → 0.68 — on the 14% of
frames where the knob is genuinely visible. Clean, and still unusable.

## Do not trust any geometry number computed from the cached track

The cached track's ellipse fit gives axis ratio 1.143 / "29° tilt". **That number is
meaningless** — it is a conic fitted to a contaminated point cloud that includes trees and
shadows. Any tilt, radius, or centre derived from a track with this many identity switches is
an artifact of the contamination, not a measurement of the scene. Diagnose detection first;
geometry means nothing until the points are the object.

## The capture fix (what to tell the user)

- Put a **coloured** marker on one knob — one that contrasts with both the yellow rig and the
  dark foliage (orange, bright green). A unique colour also resolves the opposed-knob ambiguity
  that made SAM3 hop, per `NOTES.md`.
- Or frame the wheel against the ground or open sky so no dark background crosses the orbit.
- Note the rig has **2 opposed knobs** (180° apart). Even with clean detection, an
  appearance-only tracker can swap them, which puts a π jump into θ and a huge spike into ω.
  A single distinguishable marker solves detection and identity at once.
