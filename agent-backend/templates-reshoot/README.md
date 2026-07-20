# templates-reshoot — parked phenomena, not deleted

Clips pulled out of the active corpus (`../templates/`) because **no amount of processing
recovers them** — the information is not in the pixels. Everything is preserved here
(video, sidecar, cached track, hints, evidence) so a re-shoot can reuse the framing and
skip the mistake.

**These are NOT selectable as templates.** `app/workspace.py` resolves a template by name
under `templates/`, so anything here is inert. To bring one back after a re-shoot, move the
directory to `../templates/` and delete its stale `analysis_output/api_cache.json` — a cached
track short-circuits tracking entirely (cache HIT), so a stale cache would silently make the
new video report the OLD video's numbers.

Diagnosis behind each verdict: `../docs/tracking-data-quality-2026-07-15.md` (2026-07-15).

---

## base-template-roundabout-4048 — black knob on a big playground wheel

**Verdict: unrecoverable as filmed. Needs a re-shoot.**

The target's defining feature is *darkness*, and it is filmed against dense dark foliage
that the knob's orbit crosses for the top half of every revolution. Inside the rim annulus
alone there are **~33 competing dark blobs per frame** (74,463 across 2,220 frames). A
threshold on "dark" cannot separate a black knob from a tree. The knob is separable only on
the bottom arc, against bright paving.

Evidence: `../docs/figures/mask-4048-foliage.png` — the HSV dark-mask with the rim annulus
drawn; the whole top of frame is solid foliage.

Correctly-gated tracking yields an **honest 14% coverage**. The shipped cache claims
`track_coverage: 1.0` while being wrong in ~38% of frames — **coverage is not correctness**.

### What to fix when re-shooting

- **Put a coloured marker on ONE knob** — orange or bright green; something that contrasts
  with both the yellow rig and the dark foliage. This also resolves the second problem: the
  rig has **2 opposed knobs** (180° apart), so even a clean appearance tracker can swap them,
  which puts a π jump into θ and a huge spike into ω. One unique marker fixes detection and
  identity at once.
- **Or reframe** so no dark background crosses the orbit — shoot against the paving or open
  sky.
- **Film it closer to face-on if you can.** Every clip in the corpus is tilted (3.8°–27.1°),
  and the tilt costs ~16% ripple in ω from perspective. It is fixable in software, but the
  cheapest place to fix it is the tripod.
- **Spin it for longer.** 4048 gave ~1 revolution in 37 s. Under ~2 revolutions the
  perspective artifact cannot even be diagnosed (the 1/rev and 2/rev signatures are not
  separable), which is what makes turntable-2 and -3 undecidable. **Aim for ≥3 revolutions
  of sustained motion.**

### Two real tracker bugs this clip exposed (they outlive it)

Both are genuine defects in `workspace_lib/analysis/color_track.py`, worth fixing regardless:

1. **`area × mean_saturation` scoring is invalid for a DARK target.** Black is defined by low
   *value*; its saturation is meaningless noise. The score degenerates to "biggest dark blob
   in the ROI" — a tree, a shadow, the rig. Detected bbox widths ranged 8→658 px (area CV
   2.08).
2. **`max_step: 250` where the knob moves 8.3 px/frame** (`ω·r/fps`) — 30× too loose. Observed
   p99 step was 240.9 px: the tracker used its full allowance to teleport, and because `prev`
   then follows the wrong blob, the error is **sticky**.
