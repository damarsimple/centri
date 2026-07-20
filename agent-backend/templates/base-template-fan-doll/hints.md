# Processing hints — base-template-fan-doll

> Read before Step 2. Clip-specific; takes precedence over your defaults.
> Evidence: `docs/tracking-data-quality-2026-07-15.md` §3.7.

## Verdict: NOT usable as filmed. Report `failed`. Do not produce material from it.

**Scene.** A cream plush toy (with a small green sprout on top) tied to one blade of a ceiling
fan, filmed from below against a cream ceiling. The camera swings.

## Why nothing can find the toy

**The toy is cream. The ceiling is cream.** The target's defining feature is shared with the
background — `roundabout-4048`'s failure exactly, in a different colour.

Confirmed empirically, do not repeat it: prompts `toy`, `yellow toy` and `doll` across four cuts
(`IMG_3678_10s`, `_3to10_portrait`, `_10s_portrait`, `_5s_portrait`) — **twelve combinations,
every one returning NO trajectory at all.**

> **A prior lab note claims `toy` reached 100% coverage on this clip** (vs 6% for `cream colored
> doll`). **We could not reproduce this on any variant.** Either it refers to a configuration
> since lost, or the record is stale. Do not rely on it.

## The sidecar's reference label is actively harmful

`reference_geometry.label` is `fan blade` — and SAM3 matches that text to the **window's louvre
slats**, which are literally blade-shaped, and tracks them instead of the fan (the cached
`api_cache.json` is a track of the window). This is the corpus's clearest case of the rule:

> **A noun that describes a shape will find that shape in the background.** The prompt must be
> discriminative *within the frame*, not merely accurate about the object.

## Partial recovery (documented so it is not re-attempted blind)

The toy carries a **green sprout**, and that *is* separable: sprout HSV S = 98–161 against a
ceiling median of S = 20. Colour-tracking it (`H 32–52, S ≥ 70`, predict-and-match gating, NOT
biggest-blob) lifts the clip from **0% → 51.7% coverage**, median step 2.0 px, zero teleports —
and it locks onto the real toy wherever it fires.

**51.7% is still not usable**, and the box area CV of 1.30 says why: the sprout is a
three-dimensional feature that rotates out of view for much of each revolution. The only
contrasting feature on the target is intermittently visible. **This needs a marker, not a better
algorithm.**

## The capture fix

- Attach a **flat, saturated marker** (orange/green tape) to a blade — one that contrasts with a
  cream ceiling and stays visible through the whole rotation, unlike a 3D sprout.
- Frame the fan **larger**: the toy orbits at a small radius here and the fan is distant.
- Steady the camera; it swings noticeably.
- The fan is fast — check the angular step (`ω·r/fps`) stays under ~90°/frame at 60 fps, or use
  `frequency` mode (which recovers ω without a per-frame point, but **synthesizes** the orbit —
  see the fan-4027/4028 hints).
