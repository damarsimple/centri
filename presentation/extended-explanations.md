# Centri — extended explanations of the forces, methods, and equations

The "why it works" companion to the glossary. For each item: what it is, the math or derivation, why we use it over the alternative, and where it shows up in Centri. Notation: ω angular velocity, α angular acceleration, θ angle, r radius, Δ a small change.

---

# Part 1 — The physics of circular motion

## 1.1 Angle, angular velocity, angular acceleration
Position on a circle is described by one number, the angle θ(t). Everything else is derivatives of it.

- Angular velocity: ω = dθ/dt. How many radians per second the object sweeps.
- Angular acceleration: α = dω/dt = d²θ/dt². How fast ω itself changes.

Intuition: θ is *where* it is on the circle, ω is *how fast* it goes around, α is *whether it's speeding up or slowing down*. This is the whole ladder, and Centri measures θ from the video and differentiates up the ladder.

## 1.2 Tangential speed: v = ω·r
The arc length travelled is s = r·θ (definition of a radian). Differentiate in time:
v = ds/dt = r·(dθ/dt) = r·ω.
So a point farther from the axis (bigger r) moves faster for the same ω. This is why the tip of a fan blade is fast while the hub barely moves, even though both share one ω.

## 1.3 Centripetal acceleration: a_c = ω²·r = v²/r
This is the one to be able to derive, because it's the heart of the topic.

Write the position as a vector that goes around a circle at steady ω:
**r**(t) = r·(cos ωt, sin ωt).
Differentiate once for velocity:
**v**(t) = r·ω·(−sin ωt, cos ωt) → speed |v| = r·ω (matches 1.2).
Differentiate again for acceleration:
**a**(t) = −r·ω²·(cos ωt, sin ωt) = −ω²·**r**(t).

The acceleration points *opposite* to the position vector, i.e. straight back toward the centre, and its size is
a_c = ω²·r.
Using v = ωr you can rewrite it as a_c = v²/r. Both forms are the same fact.

Key idea to say out loud: even at constant speed, the *direction* of velocity is always changing, and a changing velocity vector is an acceleration. That acceleration is centripetal, always inward.

## 1.4 Centripetal force: F = m·a_c = m·ω²·r
Acceleration needs a force (Newton's second law). The centripetal force is not a new kind of force; it's whatever real force happens to point inward and hold the object on the circle:

- Bicycle marker: the structural/adhesive force from the tyre it's stuck to.
- Phone on the turntable: static friction between phone and disc.
- Toy on the fan blade: tension in its attachment plus the blade's support.

If that inward force can't supply m·ω²·r, the object can't stay on that circle: the phone slides off, the toy flies outward. This is a good, concrete thing to mention.

## 1.5 Centrifugal force (so you can answer the trap question)
There is no outward "centrifugal force" in the normal (inertial) frame. The only real force is the inward centripetal one. "Centrifugal" is the *apparent* outward push you feel only when you sit in the rotating frame; it's a bookkeeping term (a pseudo-force), not a physical pull. The doll on the fan swinging outward is not a centrifugal force throwing it out; it's the hanging doll settling at a larger radius because, as ω rises, that's the new equilibrium where the inward force matches m·ω²·r.

## 1.6 Tangential acceleration and total acceleration
If ω is changing, the *speed* is changing too, which adds a second acceleration component along the direction of motion:
a_t = dv/dt = r·(dω/dt) = r·α.
So at any instant a rotating object can have two accelerations at right angles:
- a_c = ω²·r, pointing inward (always present while it turns),
- a_t = α·r, pointing along the circle (only when speeding up or slowing down).
Total magnitude: a = √(a_c² + a_t²).
For the bicycle, α ≈ 0 so a_t ≈ 0 and only a_c matters. For the fan and turntables both are present, which is exactly why those cases are richer.

## 1.7 Period and frequency
Period T is the time for one full turn; frequency f is turns per second.
T = 2π / ω, f = 1/T = ω / 2π.
One revolution is 2π radians, so dividing by ω (radians per second) gives seconds per revolution.

## 1.8 Constant-α kinematics, and why it links to the curve fit
If α is constant, integrate it:
ω(t) = ω₀ + α·t, then θ(t) = θ₀ + ω₀·t + ½·α·t².
So under constant angular acceleration, **θ(t) is a parabola in time**. This is the exact reason Centri classifies motion by fitting θ(t) to a parabola: the coefficient of t² is α/2, so a good parabola fit both detects non-uniform motion and reads off α directly. Uniform motion is the special case α = 0, where θ(t) is just a straight line.

---

# Part 2 — From pixels to motion

## 2.1 Getting the angle: atan2 (and why not plain tan/atan)
Each frame gives the object's pixel position (x, y). Relative to the rotation centre (cx, cy):
dx = x − cx, dy = y − cy.
The angle of that vector is
θ = atan2(dy, dx).

Why atan2 and not atan(dy/dx):
- Plain arctan only returns angles in (−90°, +90°), so it can't tell left from right; points on opposite sides of the circle collapse to the same value.
- It divides by dx, which blows up when dx = 0 (top and bottom of the circle).
- atan2 takes dy and dx separately, uses their signs to place the angle in the correct one of all four quadrants, and is defined everywhere. It returns the full (−π, π] range.

So "using tan to calculate the movement" really means: take the arctangent of the vertical-over-horizontal displacement from the centre, done the safe way with atan2, to recover where on the circle the object is each frame.

## 2.2 Unwrapping the angle
atan2 jumps from +π back to −π every time the object crosses the same spot. If you differentiated that raw signal you'd get a huge fake spike once per revolution. "Unwrapping" detects those 2π jumps and adds or subtracts 2π so θ grows smoothly and monotonically across many revolutions. After unwrapping, θ(t) is a clean rising curve you can differentiate and also use to count total revolutions.

## 2.3 Numerical differentiation to get ω
We don't have a formula for θ(t), only samples per frame, so we differentiate numerically with a central difference:
ω[i] ≈ (θ[i+1] − θ[i−1]) / (2·Δt), with Δt = 1/fps.
Central differences are more accurate than one-sided ones. The catch: differentiation amplifies noise (a tiny wiggle in θ becomes a big wiggle in ω), which is why smoothing comes first.

## 2.4 Savitzky–Golay smoothing
A moving average smooths but also flattens real peaks and trends. Savitzky–Golay instead slides a window along the data and, at each position, fits a low-order polynomial (we use order 3) by least squares, then takes the polynomial's value at the centre point. Because it fits a curve rather than averaging, it removes noise while preserving the shape of genuine features. We apply it to θ (window ≈ fps/6) before differentiating, so the ω we get is stable.

## 2.5 Median filter
After differentiating we run a median filter on ω: replace each value with the median of its small neighbourhood. The median ignores a single wild outlier (an impulse spike from one bad frame) completely, whereas a mean would smear that spike into its neighbours. So it cleans isolated spikes without blurring the real signal.

## 2.6 Calibration: pixels to metres
The video measures pixels; physics wants metres. We use a reference object of known real size visible in the scene:
px_per_m = diameter_in_pixels / real_size_in_metres,
then any pixel length becomes metres by dividing: r_m = r_px / px_per_m. This assumes the reference sits at roughly the same distance/scale as the orbit (no strong perspective). It's the single place real-world scale enters, and it's why absolute accelerations are only as good as that size measurement, while angular quantities (which are scale-free) are exact regardless.

---

# Part 3 — Fitting the circle

## 3.1 The problem
We have a cloud of tracked points and want the circle they lie on: its centre (the rotation axis) and radius. Two complications: a few points are wrong (blur, momentary mistracks), and the human-tapped centre may be off. So we need a fit that ignores bad points.

## 3.2 Circumcircle from three points
Any three non-collinear points define exactly one circle through them (the circumcircle). Given points p₀, p₁, p₂, the centre (ux, uy) is the intersection of the perpendicular bisectors of the chords, which solves to a determinant formula:
D = 2·[x₀(y₁−y₂) + x₁(y₂−y₀) + x₂(y₀−y₁)],
ux = [ (x₀²+y₀²)(y₁−y₂) + (x₁²+y₁²)(y₂−y₀) + (x₂²+y₂²)(y₀−y₁) ] / D,
uy = [ (x₀²+y₀²)(x₂−x₁) + (x₁²+y₁²)(x₀−x₂) + (x₂²+y₂²)(x₁−x₀) ] / D,
radius = distance from (ux, uy) to any of the three points. (D = 0 means the points are collinear, so that sample is skipped.) This is the per-iteration building block of RANSAC.

## 3.3 RANSAC (RANdom SAmple Consensus)
The robust fit. The loop:
1. Randomly pick 3 points and compute their circumcircle (3.2).
2. Count how many of *all* the points lie within a tolerance band of that circle (within 8 px of the radius). Those are the inliers.
3. Keep the circle with the most inliers; repeat for many iterations (we run 1000).

Why it's robust: outliers don't agree with each other, so a circle fit through good points collects a large consensus while a circle pulled toward a bad point collects few inliers and loses. It finds the model the majority supports rather than the one that minimises total error (which a single outlier can dominate).

Degeneracy guard: three nearly-collinear points define a gigantic circle, and a giant circle is locally almost a straight line, so it can accidentally "fit" an arc of points and report a huge bogus radius. We reject any fit whose radius is more than twice the farthest point's distance from the marked centre, which throws those out.

## 3.4 Least-squares (algebraic) circle fit, the alternative
The non-robust option, for contrast. Write the circle as x² + y² + D·x + E·y + F = 0 and solve the linear least-squares system for D, E, F over all points at once (the Kåsa fit). It's fast and gives a single closed-form answer, but every point votes equally, so one outlier bends the result. We use this style only as a refinement once the inliers are known; RANSAC does the robust job first. Saying "we use RANSAC because least squares is outlier-sensitive" is the clean one-line justification.

## 3.5 Residual, and the coefficient of variation (CV)
After fitting, the residual of each point is how far its distance-from-centre differs from the fitted radius. A tight fit has small residuals. We summarise the spread of per-point radius with the coefficient of variation:
CV = standard deviation of radius / mean radius.
CV is unitless, so it's a clean "how circular is this really" score. A correct centre gives low CV; a wrong centre makes the same circular path look like the radius is pulsing, inflating CV.

## 3.6 The centre-override rule, and why it's safe
We keep the human-tapped centre unless the fitted centre is *unambiguously* better, defined by two conditions that must both hold:
1. the fit's inlier residual ratio is small in absolute terms (tight), and
2. the radius CV around the fit is much lower than around the mark (CV_fit < 0.6 × CV_mark).
This is self-guarding. A correct human tap already gives low CV, so condition 2 fails and we keep it. A degenerate fit gives high CV, so it fails too. Only a genuinely off mark paired with a genuinely good fit passes both, which is exactly what happened on the fan (mark 158 px off, CV 39% → 10%).

---

# Part 4 — Classifying the motion (uniform vs accelerating)

## 4.1 Line vs parabola fit on θ(t)
From 1.8: constant ω means θ(t) is a line; constant α means θ(t) is a parabola. So we fit θ(t) twice, with a degree-1 and a degree-2 polynomial (ordinary least squares), and compare how well each explains the data. The t² coefficient of the parabola is α/2, giving α directly.

## 4.2 R² and residual-variance reduction
R² (coefficient of determination) measures the fraction of variation a model explains:
R² = 1 − (variance of the residuals) / (variance of the data).
R² = 1 is a perfect fit. We declare the motion non-uniform only when the parabola cuts the residual variance by more than 70% versus the line **and** ω actually changes appreciably across the clip (|α|·duration / mean-ω > 0.3). Both guards stop us from calling slightly noisy steady motion "accelerating."

## 4.3 Why fit θ, not the derivative of ω
You could try to detect acceleration by thresholding dω/dt, but that's the second derivative of noisy data, so it flickers wildly (this is exactly the bug we fixed). θ is the *integral* side: smooth and stable. Fitting a parabola to the smooth θ recovers α far more reliably than differentiating ω twice. This is a strong, concrete methodological point.

---

# Part 5 — The evaluation math

## 5.1 Cosine similarity
The basic similarity between two vectors a and b:
cos(a, b) = (a · b) / (|a|·|b|),
the cosine of the angle between them. 1 means same direction (identical meaning, for embeddings), 0 means unrelated. It ignores magnitude and looks only at direction, which is what we want for comparing meanings.

## 5.2 BERTScore (precision, recall, F1)
Older metrics count exact word overlap, so "tyre" and "wheel" score zero together. BERTScore fixes this:
1. Embed every token of the candidate and of the reference with a contextual model (RoBERTa), so each word's vector reflects its sentence.
2. For each candidate token, take its highest cosine similarity to any reference token, and average those: that's precision P.
3. For each reference token, take its highest similarity to any candidate token, and average: that's recall R.
4. Combine: F1 = 2·P·R / (P + R), the harmonic mean.
It's "soft" token matching by meaning. Our material vs the OpenStax 6.2 reference gives whole-passage P 0.837 / R 0.842 / F1 0.840 ± 0.002 across 5 runs (3 phenomena: turntable ×3, bike, fan; highest per-section on "how the variables relate", 0.855 — the formulas the textbook shares). We use it only for comparability with the paper, not as a quality claim — the quality half (judge + teacher panel) is designed but not yet run.

The prior method's Table 3 reports five automatic metrics: BERT P, R, F1, a diversity score, and an LSTM language-fluency score. We reproduce four — P/R/F1 (above) and diversity (0.204) — and omit the LSTM score, which needs the prior method's own trained LSTM model that we don't have; we won't substitute a non-comparable proxy. Their overall F1 is 0.882, but that's question-vs-prompt against a different reference, so it isn't a head-to-head number with our material-vs-textbook 0.840.

The roadmap is to widen this automatic battery (see the "next plan" slide): **BLEU** (lexical n-gram precision against the reference), **ROUGE-1/2/L** (content recall — how much of the reference appears in the output), and **BLEURT** (a learned, model-based quality score). BLEU/ROUGE are lexical, so paraphrased-but-correct material scores lower on them by construction — which is exactly why they are complementary diagnostics (coverage, precision) rather than the headline; BLEURT and the human panel carry the quality judgement.

## 5.3 Reference and granularity (and why it isn't rigged)
The reference is a real, published textbook section — OpenStax College Physics §6.2 (Centripetal Acceleration) — *reorganized* into our five-section format. Three points make this a fair gold reference rather than a self-comparison: (1) it is the **authentic textbook text**, reorganized to our structure but **not paraphrased** — we do not diff the raw PDF, we align it section-by-section so a per-section score is even meaningful; (2) the reorganization was done **independently of our generation** — the give-away is that the textbook's "what the video shows over time" section is its own car/centrifuge worked examples, not our measured numbers, so nothing leaks in to inflate the score; (3) we report the **whole passage** (the headline) as well as each section (diagnostic), so the comparison is not selective. The conceptual sections (variables, relationships) align tightly with the textbook; the grounded sections (scenario, what-the-video-shows, figures) score lower because they are our value-add the textbook lacks. Swapping in the co-author's preferred reference keeps the method identical. (Diversity, the spread within a set, is not emphasized for material — passages on one topic with one structure are similar by design.)

## 5.4 Statistics quick reference
- Pearson r: linear correlation, r = cov(x, y) / (σx·σy), range −1 to 1. Used for video-vs-gyroscope and automatic-vs-human agreement.
- Cohen's / Fleiss' κ: agreement beyond chance, κ = (p_observed − p_chance) / (1 − p_chance). For the teacher panel.
- ANOVA: compares group means via F = between-group variance / within-group variance. For difficulty × format conditions.
- ANCOVA: ANOVA after regressing out a covariate (the pre-test), so you compare adjusted means. The learning study's main test.
- Effect sizes: Cohen's d = (mean₁ − mean₂) / pooled SD; η² = effect sum-of-squares / total sum-of-squares. They say *how big* the effect is, not just whether it's significant.

---

# One-paragraph version of each, if you're put on the spot
- **a_c = ω²r:** velocity direction changes even at constant speed; that change is an inward acceleration of size ω²r.
- **atan2:** quadrant-safe arctangent of (dy, dx) from the centre, gives the angle each frame; plain tan loses the quadrant and divides by zero.
- **RANSAC:** fit a circle from 3 random points, count agreers, keep the most-agreed circle; robust because outliers never form a consensus.
- **Centre override:** trust the fit over the tap only when it's both tight and far less wobbly, so a good tap is never overruled.
- **Parabola fit:** constant α makes the angle quadratic in time, so a parabola beating a line by a wide margin means the spin is accelerating, and its t² term is α/2.
- **BERTScore:** soft, meaning-based token matching into precision, recall, and F1; kept only for comparability.
