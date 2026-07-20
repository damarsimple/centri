# Processing hints — base-template-bicycle

> Read before Step 2. Clip-specific; takes precedence over your defaults.
> Evidence: `docs/tracking-data-quality-2026-07-15.md` §3.6, §4.2.

**Scene.** A phone threaded through the rear-wheel spokes of a bicycle on a stand, spun by hand
and coasting down. The wheel is **vertical**. Verified frame-by-frame 2026-07-15.

## Detection is good — leave it alone

100% coverage, zero teleports, box area CV 0.18, 6.4 revolutions of active motion. The tracker
follows the phone correctly throughout. Do not re-prompt or change `tracking_mode`.

## OPEN PROBLEM: ω has a phase-locked ripple nobody has explained

This is the **only clip in the corpus with an unexplained artifact**. Report its per-instant
ω(t) with caution, and do not claim the ripple is either real physics or an error — we do not
know which.

| signal | value |
|---|---|
| ripple CV | 0.141 |
| phase-lock | **0.72** (over 6.4 revolutions) |
| fingerprint | A1=0.846, A2=0.286 (1/rev dominant) |
| hub offset | **4.9 px** |

**Do NOT rectify it.** The imaged wheel hub was detected in 90% of frames and verified; at a
4.9 px offset from the ellipse centre the view is essentially affine, so there is no perspective
to undo. Measured: rectification moves ripple CV 0.141 → 0.148 and makes the radial residual
*worse* (3.94% → 4.47%). The 1/rev-dominant fingerprint looks like perspective and is not —
which is exactly why the hub offset, not the fingerprint, is the discriminator.

**Do NOT filter it either.** It is phase-locked, therefore deterministic; a low-pass that removes
it also destroys whatever real trend it sits on.

### What has been ruled out

- **Perspective** — hub offset 4.9 px (4046, which does have it, is 85.6 px).
- **Periodic occlusion** — the phone passes behind the frame and derailleur once per revolution,
  which would cut the mask and shift its centroid. Tested: visible area vs orbital phase gives
  **R² = 0.073**, with a 1/rev amplitude of only 5.9% of mean area. Rejected.
- **Gravity (partly)** — the wheel is vertical and the phone is a heavy mass at radius, so
  gravity should speed it up descending and slow it climbing. Energy conservation predicts ω²
  linear in height: the **sign is right** (higher ⇒ slower) but R² = 0.35, and ω peaks
  **138° away** from the bottom of the wheel, where gravity requires the maximum. Not the (whole)
  explanation.

### Leading untested hypothesis

The tracked object is **extended, not point-like**: the phone's box is ~126 px across while its
orbit radius is only ~121 px — **size ≈ orbit radius**. A mask centroid may not be a faithful
orbit tracer at that ratio. Untested; do not state it as a finding.

Note the caveat on the evidence itself: phase-lock 0.72 over 6.4 revolutions is weaker than
4046's 0.94 over 18.6, so part of it may be the statistic's own variance.

## If you re-shoot this phenomenon

- Attach a **small** marker (a bright dot, not a phone) so object size ≪ orbit radius.
- Mount it near the **rim**, not near the hub — this clip's orbit radius is only 121 px.
- Keep the camera face-on and steady; aim for ≥3 revolutions of sustained coast-down.
