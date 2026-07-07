# Ideal learning-material example — the target "what good looks like"

Design reference for the tiered material rework (see
[`difficulty-tiered-material-spec.md`](difficulty-tiered-material-spec.md) → Addendum
2026-07-08). It instantiates the canonical nine-section structure on a **real** decelerating
clip — *a black handle on a playground wheel* (job `1946a285`), the same scene as the
learning-material critique — so every number below is measured and closes.

All arithmetic here is produced **deterministically** by `material_seed.build_seed()` and
rendered by `render/report.py`; the 35B never authors it. To regenerate the concrete PDF,
run `analysis.material_seed` → `analysis.render.figures` → `analysis.render.report` in the
job workspace and compile `student_edition.advanced.tex`.

## Verified reference numbers (black handle)

| Quantity | Value | Note |
|---|---|---|
| r (fitted) | 0.246 m (461.0 px @ 1875 px/m) | one merged table row (A9) |
| ω (canonical) | 7.81 rad/s | `stable_mean_omega` — prose == table (A2/A4) |
| a_c (mean) | 15.6 m/s² | |
| α | −0.205 rad/s² | fit R² = 0.99998 |
| **a_t = α·r** | **−0.0505 m/s²** | **signed** — negative in a deceleration (A3) |
| ω initial → final | 9.33 → 6.25 rad/s | ends at 6.25, so `comes_to_rest = false` (A7) |
| T, f | 0.837 s, 1.195 Hz | measured, mutually consistent (`T = 1/f`) |
| circumference 2πr | ≈ 1.55 m | basic worked example |
| laps in clip | ≈ 18 | basic worked example (f·duration) |
| ⟨ω⟩²·r vs ⟨ω²⟩·r | 15.0 vs 15.1 m/s² | Jensen: ⟨ω²⟩·r closer to measured 15.6 |
| extrapolated stop | ≈ 30 s after clip end | it has NOT stopped within the clip |

## Canonical nine-section skeleton (every tier, same order)

1. Header & metadata (object, direction, clip length, difficulty badge)
2. **Learning objectives** — deterministic, per tier
3. Scenario (LLM prose; motion-aware — never "steady" on a slowing clip, A1)
4. The variables we measured (+ measurements table)
5. How the variables are related (concepts/formulas)
6. **Worked examples** — deterministic, house Given/Formula/Substitute/Result/Interpret
   format; intermediate/advanced use seeded LaTeX in real math mode, basic is symbol-free
7. What the video shows over time / Reading the figures (LLM prose + figures)
8. **Measurement honesty box** — shaded box; averages-vs-instant, Jensen, calibration
9. **Check your understanding** — deterministic Q + answer key, then the tier bridge

Sections 2/6/8/9 are rendered straight from `material_seed.json` (correct by construction);
the odd sections are the LLM's grounded prose. This is why the arithmetic can never drift.

## Tier depth (what changes)

- **Basic** — symbol-free. Turns-per-second *with the unit* ("about 1.2 full turns each
  second", never a bare "7.80 per second", A5); narrates only the supplied angle milestones
  (A6); one honesty sentence.
- **Intermediate** — v=ω·r, a_c=ω²·r verified at one timeline instant, T=1/f; honesty box adds
  why the identity doesn't close on averages.
- **Advanced** — α, signed a_t, the ⟨ω²⟩>⟨ω⟩² argument, the extrapolated stopping time (only
  because it has not yet stopped), the calibration-independence question; full Jensen +
  calibration honesty box.
