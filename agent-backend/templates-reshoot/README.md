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
  exactly as the red marker did for `computerfan-4029`.
  *(Corrected 2026-08-06: this line used to read "for both fans". It was wrong —
  `computerfan-4029` is the only marker-tracked fan. `fan-4027`/`fan-4028` ran in `frequency`
  mode with no tracked point at all, and `fan-doll` failed outright. They are parked below.)*
- **Fill the frame with the wheel** so the knob is well over 38 px, which may also bring SAM3 in.
- **Tape the rim diameter.** There is no object of known size in frame, so every SI value is
  provisional (ω, T, f are scale-free and unaffected).
- Keep the framing still: the source is usable only to ~45 s; after that the operator pans and
  pulls back, and the imaged wheel diameter falls from ~1020 px to 762 px.

---

## base-template-fan-4027 and base-template-fan-4028 — 5-blade ceiling fans, `frequency` mode

**Verdict: superseded 2026-08-06. Re-shot successfully as `templates/base-template-fan-4656`.**

Not parked for a tracking failure — parked because **they never had a trajectory to fail**.
Both ran `tracking_mode: frequency`, which recovers ω from blade-pass frequency and then
**generates** a circular orbit from it. The tell-tales are in each directory's own `hints.md`:
orbit axis ratio exactly 1.000, bbox area CV exactly 0.00. Between them they produced six
worksheets built on a manufactured orbit, drawn on the frame as if it had been observed.

Two independent problems, both now fixed by the reshoot rather than by a parameter:

1. **No measured position.** ω, T and f were legitimate; a per-frame *position* was not, and
   neither were v, a_c or anything drawn as a path.
2. **The rate floor.** `frequency` mode reports rotation while the object is at rest. Measured
   on the replacement clip's stationary tail, a blade-pass FFT returns **4.69 rad/s** on frames
   where the marker track correctly returns **0.016** — see
   `templates/base-template-fan-4656/NOTES.md` §3.

The replacement carries a yellow card marker on one blade, tracks in `color` mode at
**99.99% coverage with zero jumps over 190.8 revolutions**, and agrees with an independent
blade-pass measurement of ω to **under 1%** on every steady window.

`fan-4027` additionally carries the documented `diameter_px`-holds-a-RADIUS trap that halved
every SI value on one real run (`job_fan-4027-r2`). If either clip is ever revived, read its
`hints.md` calibration section first — and delete `analysis_output/data/api_cache.json`, or a
cached track will silently make new footage report the old footage's numbers.

### What to fix if these are ever re-shot rather than replaced

- **A marker on one blade** — flat, saturated, large. That is the whole fix; it converts the clip
  from `frequency` to `color` and gives it a real trajectory. Already proven on `fan-4656`.
- **Get closer to face-on.** `fan-4656` still sits 34.5° off, which costs a ±19% ripple on
  instantaneous ω and has to be rectified out.
- **Put a ruler, or a strip of tape of known length, flat on a blade in the plane of rotation.**
  On `fan-4656` this turned out not to be needed — the card *is* the ruler once its orientation
  and its outer edge are pinned — but a known-length span in frame would have saved a long
  reconciliation.

---

## basetemplate-turntable-3 — red phone on a turntable

**Verdict: withdrawn 2026-08-06. The tracked point teleports; the published numbers were 27% wrong.**

Removed from the corpus on Damar's call, not repaired. The marker's normal frame-to-frame step is
**1.4 px**, but it jumps **604 / 614 / 713 px in a single frame** at t = 0.85 / 1.74 / 2.08 s,
flipping between two positions 728 px apart. One of those jumps sits **inside the active window**,
so 18 of 106 active samples are contaminated. Smoothing spreads each step into a symmetric ramp
(~±12 frames), which is why they render as mountains and why ω climbs 0 → 10.2 rad/s while the
tracked position is frozen to 0.1 px.

Effect on the delivered numbers: **mean a_c 7.45 → 5.85, max 31.06 → 18.12.** The worksheets
taught 7.45, which is **27% above the jump-free value**.

Two further problems were never separated from that one:

1. **A second ~31% effect from the radius.** The sensor validation was run on
   `job_turntable-3-RECT` (`r_fit_m` 0.1477) while the shipped worksheets came from the
   unrectified `job_turntable-3` (`r_fit_m` 0.2037) — a 38% radius gap. Because `a_c ∝ r`,
   rectification and jump-rejection may be double-counting one error or may be two independent
   ~30% errors. Nobody separated them.
2. **An unexplained mid-coast speed-up** (v 0.73 → 1.92 m/s during a coast-down) outside every
   jump-contaminated window. Ruled out: marker centroid, motion blur, perspective, wrong centre,
   real torque, and SAM3's masks specifically (LocateAnything-3B reproduces it). Still open.

### What to fix when re-shooting

- **A flat, high-contrast marker that cannot be confused with a second object.** The scene holds a
  red phone, a steel ruler and a hand entering frame; the tracker alternates between two positions
  728 px apart, so a second candidate is plausible though never proven. Diagnosing that needs the
  raw detection boxes, not the kinematics.
- **Spin for longer.** At ~1.5 revolutions the perspective artifact cannot even be diagnosed — the
  1/rev and 2/rev signatures are not separable. Aim for ≥3 revolutions, as for the park wheel.
- **A ruler or known-length tape in frame**, so the metre scale does not depend on the same fit
  that the rectification changes.

**Nothing in the delivered pipeline rejects a jump.** The sweep that found these was written by
hand for a memo; a guard against a marker moving 500× its usual step is still UNBUILT
(`TODO.md` §5.1). Detect against the clip's OWN local median step — a fixed px threshold is
useless, because `computerfan-4029` legitimately moves ~240 px/frame at peak.
