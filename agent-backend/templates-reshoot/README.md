# templates-reshoot — parked phenomena, not deleted

Clips kept out of the active corpus (`../templates/`) because they do not currently yield a
trustworthy measurement — either the information is not in the pixels at all, or we have no
tracking method that follows the object. Everything is preserved here (video, sidecar, cached
track, hints, evidence) so a re-shoot can reuse the framing and skip the mistake.

**`../templates/` is GOLD only** (2026-07-21, Damar): a clip earns a place there once its
per-frame trajectory is measured and verified, not before. A promising clip with no working
tracker waits here, so nothing selectable can produce numbers we would not stand behind.

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

---

## base-template-parkwheel-4091 — park exercise wheel ("大輪"), two orange knobs

**Verdict: good footage, no tracker that follows it. Needs one strip of coloured tape.**

The motion is the best in the corpus on paper — **27.4 revolutions in 65 s**, a clean monotonic
coast-down (ω 4.85 → 2.43 rad/s), and the only clip that comes to **rest inside the recording**.
It is parked anyway, because all three tracking methods were tried on the 30 s cut and measured:

| method | result |
|---|---|
| SAM3 object | **returns nothing** — six cues (`ball`, `orange ball`, `handle`, `knob`, `orange knob`, `grip`) all empty on a 4 s probe. The knob is ~38 px in a 1080×1920 frame. |
| colour | locks onto the rig's own sunlit red base: **100% coverage, zero rotation**. With an annulus ROI and a size ceiling the orbit is real (r 507 px, 4°/frame, no π jumps) but coverage is 11–52%. |
| frequency | flat ω ≈ 3.1–3.3 rad/s, contradicting both the visible coast-down and the chord measurement below. |

**It also has real perspective: hub offset ≈ 60–73 px** (roundabout-4046 = 85.6 px; clips needing
no correction = 0.7–8.8 px), so even with a working tracker its per-instant ω would carry a 1/rev
projection ripple. Second clip that makes the rectification fix worth doing.

Geometry, measured by intersecting 205 knob-pair chords (the two knobs are a physical diameter,
so the line joining their images passes through the image of the axle at any viewing angle) and
reading the pair-axis angle mod π (immune to the 180° identity swap): hub **(547, 977) px**,
orbit radius **510 px**, axis ratio 0.96 (tilt ≈ 16.5°). Full detail in the directory's `NOTES.md`.

### What to fix when re-shooting

- **Tape one knob in a saturated colour that is not the rig's red** — bright green. The rig is
  red/silver/yellow, and its red cap and base are 30k+ px of the same hue as the knobs, which is
  what defeats colour tracking. One marker fixes detection AND the two-knob identity swap at once,
  exactly as the red marker did for both fans.
- **Fill the frame with the wheel** so the knob is well over 38 px, which may also bring SAM3 in.
- **Tape the rim diameter.** There is no object of known size in frame, so every SI value is
  provisional (ω, T, f are scale-free and unaffected).
- Keep the framing still: the source is usable only to ~45 s; after that the operator pans and
  pulls back, and the imaged wheel diameter falls from ~1020 px to 762 px.
