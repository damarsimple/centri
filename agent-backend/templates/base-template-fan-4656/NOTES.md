# base-template-fan-4656 — tracking study, 2026-08-06

Source: `drive-download-20260805T075107Z-1-001/IMG_4656.MOV` (reshoot of the ceiling fan with a
yellow card marker, requested by `templates-reshoot/README.md` and `TODO.md` §1.2).
1920×1080, 59.924 fps, 13,781 frames, 230.0 s, HEVC. No rotation metadata.

All numbers below were produced **outside the pipeline** (plain OpenCV prototypes), then
reproduced through the shipped `analysis.color_track` with the sidecar in this directory.

## 1. Which of the four reshoot clips

| | IMG_4654 | **IMG_4656** | IMG_4657 | IMG_4655 |
|---|---|---|---|---|
| framing | portrait, handheld, hand in frame | landscape, tripod-ish | landscape | — |
| detections on-orbit | 37% | **100.00%** | 99.8% | — |
| circle-fit residual | 44% of r | **7.0%** | 8.7% | — |
| revolutions | 56 | **190.8** | 86.9 | — |
| max Δθ/frame (Nyquist 180°) | 173° | **34.3°** | 130.5° | — |
| steps > 8× median | 98 | **0** | 14 | — |

- **IMG_4655** is 2.7 s of a face — discard.
- **IMG_4654** has wooden ceiling louvres in the same hue band as the marker, a hand reaching
  into frame, and camera motion (so a static-distractor map cannot be built). Unusable as filmed.
- **IMG_4657** is good but occasionally locks onto the wooden window frame at the left edge.
  Same scene as 4656 at a slightly larger tilt (37.4°). Keep as a spare, do not promote.

## 2. Detector

Plain HSV band `H 10–35, S ≥ 90, V ≥ 90`, largest blob, ROI disc r = 330 px about the hub.
Marker blob area ≈ 11–12 k px — against the next-largest in-ROI blob at **11 px**, a separation
of roughly 1000:1. (In IMG_4657 the same threshold leaves an 11,035 px window-frame blob, which
is why that clip jumps and this one does not.)

Verified through the shipped tracker with **only the keys the orchestrator forwards**
(`hsv_lo`, `hsv_hi`, `roi_radius`, `min_area` — no `roi_inner`, no `max_area`, no `max_step`):

```
coverage 99.99%   on-orbit 100.00%
ellipse semi-axes 260.0 / 214.2 px   centre (902.3, 502.1)
step med 23.4 px   max 141 px   jumps > 8× median: 0
190.8 revolutions   max Δθ 34.3°
```

## 3. Independent check on ω — blade-pass frequency

A second measurement of the same quantity using **no marker and no tracker**: the intensity of a
single 12×12 px patch at 0.6 r, FFT'd, dominant peak divided by 5 blades.

| window | marker track (rad/s) | blade-pass FFT (rad/s) | diff |
|---|---|---|---|
| 10–22 s | 11.043 | 11.678 | −5.44% *(spin-up: ω changes across the window)* |
| 44–56 s | 7.288 | 7.224 | +0.88% |
| 78–90 s | 6.199 | 6.190 | **+0.16%** |
| 112–124 s | 6.172 | 6.170 | **+0.03%** |
| 146–158 s | 5.046 | 4.997 | +0.99% |
| 180–192 s | 1.331 | 1.335 | −0.34% |
| 214–226 s | **0.016** | **4.690** | *see below* |

Two unrelated principles agreeing to **under 1% on every steady window**. This is the corpus's
first independent rate validation on a fan.

**The last row is a result, not a failure.** The fan is at rest; the marker track says so, and
the blade-pass FFT reports 4.69 rad/s anyway. That is the `frequency`-mode floor described in
`TODO.md` §1.2 ("reports spinning while the object is at rest"), measured directly, on the same
frames, against a method that gets it right. It is the strongest available argument for why
`fan-4027`/`fan-4028` had to be replaced rather than kept and disclosed.

## 4. Geometry

Orbit residual decomposed against θ:

| harmonic | amplitude | reading |
|---|---|---|
| 1/rev | 4.1 px | hub is well centred — no decentering artifact |
| **2/rev** | **19.3 px** | **viewing tilt (the orbit is an ellipse)** |
| 3/rev | 2.0 px | — |
| 4/rev | 3.3 px | — |
| total sd | 17.5 px (7.0% of r) | |

Axis ratio 0.824 → **34.5° off face-on**, giving a ±19% ripple on instantaneous ω if left
uncorrected. Clean single effect, nothing confounding it.

## 5. The metre scale — RESOLVED 2026-08-06 to ±5%

**Answer: `px_per_m ≈ 591`, hub → card centre ≈ 0.44 m.** Reached by fixing the geometry rather
than by re-shooting. Two facts did it, both from Damar and both confirmed against the pixels:

1. **The card lies along the blade.** Its long axis is **4.2°** off radial (median over 166
   frames), so its 25 cm runs radially — the card covers a 25 cm *stretch* of blade, it is not a
   point.
2. **The card's outer edge is the blade tip**, not beyond it. Checked: card outer edge =
   `Rc + L/2` = 260.0 + 69.5 = **329.5 px**; blade-tip ellipse semi-major measured independently
   from 800 tip points = **319.3 px**. **Agree to 3.2%.**

So the card occupies the **outer 25 cm** of the blade — inner edge 31 cm (Damar's measurement),
centre ~44 cm, outer edge = tip.

| span | px | hand | implied px/m |
|---|---|---|---|
| card inner edge | 190.5 | 31 cm | 615 |
| card length | 139.0 | 25 cm | 556 |
| **least squares on both** | | | **591** |
| hub → card centre *(the sidecar value)* | 260.0 | **→ 44.0 cm** | |
| blade tip *(prediction)* | 319.3 | **→ 54.0 cm** | |

**Open, cheap, worth doing:** measure hub-axle-centre → blade tip on a bare blade. The pixels say
**~54 cm**. 51 cm would make the 25 cm card measure 22.2 cm in the same frame (−11%); 61 cm would
make it 26.6 cm (+6%). A reading well outside 52–56 re-opens this.

**What this cost:** the sidecar first carried `physical_size = 0.31`, reading Damar's figure as
hub→card *centre* when it is hub→card *inner edge*. That is `px_per_m` 839 against the correct
591 — **40% high**, making every SI length **29% too small**, and `a_c = ω²r` with it. Caught
before any worksheet was generated. The lesson is the project's existing one restated: *the two
spans must describe the same thing*, and "distance to the marker" is ambiguous the moment the
marker is bigger than a point.

### 5c. Superseded: the earlier "does not close" analysis

Hand measurements (Damar, 2026-08-06): hub→blade tip **51 cm**, hub→marker centre **31 cm**,
marker card **25 cm long × 18.5 cm wide**.

| span | hand | pixels | implied px/m |
|---|---|---|---|
| hub → marker centre | 31 cm | 260 px (orbit semi-major) | **839** |
| hub → blade tip | 51 cm | ~311 px (sectors near the major axis) | 610 |
| marker long side | 25 cm | 139 px (`minAreaRect`, rotation-invariant) | 556 |
| marker short side | 18.5 cm | 95 px (`minAreaRect`) | 514 |

Up to **38% disagreement**. The marker's visible yellow region is ~63% of the card in **both**
dimensions — a uniform factor, which folding alone does not explain. Candidate causes: the card
wraps over the blade so its edges curve out of view; the HSV band clips shaded edges; or one
hand measurement refers to a different span than assumed.

**Retracted from an earlier draft of this study:** *"marker width 18.5 cm ↔ 150 px gives 811 px/m,
agreeing with the orbit scale to 3.4% — the project's first two-way scale cross-check."* That
used the **axis-aligned** bbox width, which is inflated by the marker's own rotation
(W = p·|cos φ| + q·|sin φ|). The rotation-invariant width is 95 px, not 150. **There is no
two-way agreement, and the metre scale remains validated by nothing** — the standing conclusion
of `TODO.md` §1.4, unchanged by this reshoot.

The blade-tip pixel figure is itself soft: the dark-threshold disc leaks into the ceiling grid
and the second fan, and only the sectors within 25° of the major axis (median 311 px) look
trustworthy. It is reported here as an inconsistency to resolve, not as a measurement.

### 5a. It is NOT a tracker artifact — SAM3 agrees with the colour band

Tested once SAM3 came back up (2026-08-06). Cue sweep on one frame: every marker noun **misses**
(`card`, `yellow card`, `paper`, `sticky note`, `tag`, `label`, `sponge`, `block`, `marker`);
**`yellow object` hits**, as does `fan blade` and `ceiling fan`. Consistent with the project's
standing finding that cue wording dominates, and that a bare object noun fails as an honest miss.

`/track` with `yellow object` over a 3 s cut at t = 100 s: **179/179 frames, 24 s wall clock.**

| | radius from hub | bbox |
|---|---|---|
| SAM3 `yellow object` | 245.6 px | 144 × 142 |
| HSV colour band | 244.8 px | 146 × 119 |

**The two trackers agree on the orbit radius to 0.3%** (+0.8 px), with bbox areas within 1.08×.
So the tracked point is sound and the scale gap is **not** a segmentation bias.

*A hypothesis that died here, recorded so it is not re-run:* a single frame showed SAM3's box 155 px
tall where HSV saw 96 (62%, suspiciously close to the scale gap), suggesting HSV clipped the card's
shaded half and pulled the centroid inward. Over the full window there is no such radial bias.
**One frame is not a measurement.**

### 5b. Confirmed: the 31 cm is the card's INNER EDGE

Damar confirmed the card ends flush with the blade tip, which forces the reading. §5 above is the
resolved version; the sidecar carries 0.44.

A ruler was considered and rejected — at this distance its ticks do not resolve. It was not needed:
the card **is** the ruler, once its orientation and its outer edge are pinned.

## 6. What is claimable today

- **GOLD, scale-free:** ω(t), T, f, revolution count, the phase structure, direction, the rest
  band, and every ratio. Independently cross-checked to <1%.
- **PROVISIONAL, SI:** v, a_c, r in metres. Correct up to one unresolved multiplier.
