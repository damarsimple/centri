"""Kinematics, active detection, period & phase analysis (old steps 7-8).

Consolidation vs the old agent code: omega is computed ONCE here (unwrap ->
Savitzky-Golay -> gradient -> median filter) and that single series drives active
detection, summary stats, period, AND phase detection. The old code computed a
separate preliminary omega in step7 for active detection and a different one in
step8 for everything else, which is a chunk of why `stable_mean_omega` swung
2.9->6.1 rad/s on the same video.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import scipy.ndimage
import scipy.stats
from scipy.signal import savgol_filter

from . import common
from .contract import Inputs
from .geometry import Calibration


@dataclass
class Kinematics:
    t_s: np.ndarray
    r_px: np.ndarray
    r_m: np.ndarray
    theta_unwrapped: np.ndarray
    omega: np.ndarray
    v_m_s: np.ndarray
    ac_m_s2: np.ndarray
    active_mask: np.ndarray
    rotation_direction: str
    active_duration_s: float
    # Time bounds of the active window (first/last active frame) and the span of the
    # constant-alpha fit window (the longest active run _motion_model fits over). These let
    # the material report the honest deceleration timescale (alpha = Delta-omega / fit_window,
    # NOT / whole-clip duration) and detect an object that stops on camera before the clip
    # ends (active_end_s << duration_s). Left 0.0 when there is no active rotation / no fit.
    active_start_s: float = 0.0
    active_end_s: float = 0.0
    fit_window_s: float = 0.0
    # Tracked centroid in CROPPED space, AFTER outlier removal + short-gap fill —
    # the exact series the kinematics were computed from. Written to kinematics.csv
    # so figures plot points that sit on the fitted circle.
    x_px: np.ndarray = field(default_factory=lambda: np.array([]))
    y_px: np.ndarray = field(default_factory=lambda: np.array([]))
    n_interpolated: int = 0
    # summary (active intervals only)
    mean_r_m: float = 0.0
    std_r_m: float = 0.0
    mean_omega: float = 0.0
    std_omega: float = 0.0
    mean_v: float = 0.0
    mean_ac: float = 0.0
    max_ac: float = 0.0
    # period / frequency
    period_s: float = 0.0
    frequency_hz: float = 0.0
    T_primary: float = 0.0
    T_fft: float = 0.0
    period_discrepancy: float = 0.0
    # stable phase
    stable_mean_omega: float = 0.0
    stable_mean_ac: float = 0.0
    stable_omega_r2: float = float("nan")
    stable_omega_std_err: float = float("nan")
    n_stable_segments: int = 0
    increase_start_omega: float | None = None
    increase_end_omega: float | None = None
    decrease_end_omega: float | None = None
    phase_labels: list = field(default_factory=list)
    stable_segments: list = field(default_factory=list)
    # angular-acceleration model (fit over the longest active run). motion_type is
    # "uniform" (constant omega), "accelerating" (spin-up) or "decelerating".
    motion_type: str = "uniform"
    # True when omega RISES then FALLS inside the active window — an impulsive "flick"
    # (object at rest, given a spin, then coasting down), NOT a spin that decelerates from
    # the first frame. The constant-alpha fit is then taken over the coherent coast-down
    # segment only, so omega_initial is the real peak (~9.8 rad/s), not the parabola's
    # extrapolated intercept over the rise+fall (a fictitious 9.93 that contradicts the data).
    impulsive_start: bool = False
    alpha_rad_s2: float = 0.0          # signed angular acceleration
    alpha_r2: float = float("nan")     # R^2 of the constant-alpha (quadratic theta) fit
    omega_initial: float = 0.0
    omega_final: float = 0.0
    a_t_mean_m_s2: float = 0.0         # SIGNED tangential accel = alpha * r_fit_m (negative when decelerating)


def _segmented(signal, fn):
    """Apply fn to each contiguous non-NaN run of `signal` independently."""
    out = np.full_like(signal, np.nan, dtype=float)
    labeled, n = scipy.ndimage.label(~np.isnan(signal))
    for i in range(1, n + 1):
        m = labeled == i
        out[m] = fn(signal[m], m)
    return out


def _savgol_nan_safe(signal, window, polyorder):
    def fn(seg, _m):
        n = len(seg)
        if n >= window:
            return savgol_filter(seg, window, polyorder)
        if n >= polyorder + 1:
            w = n if n % 2 == 1 else n - 1
            w = max(w, polyorder + 1)
            if w % 2 == 0:
                w -= 1
            return savgol_filter(seg, w, polyorder) if w > polyorder else seg
        return seg
    return _segmented(signal, fn)


# Bridge tracking dropouts no longer than this (seconds). Motion blur during a fast
# spin makes SAM3 miss a few frames; on a circular path a short gap between two real
# detections is safe to interpolate. Longer gaps stay NaN (honest — never extrapolate).
MAX_GAP_S = 0.2


def _fill_short_gaps(x_full, y_full, cx, cy, fps):
    """Interpolate INTERIOR gaps <= MAX_GAP_S in polar (theta, r) space about the
    center, then rebuild (x, y). Polar (not linear x/y) because the motion is
    circular: theta is ~linear in time over a short gap and r ~constant, so the
    filled points land ON the orbit rather than on a chord. Only fills between two
    real detections; never the leading/trailing ends. Returns (x, y, n_filled)."""
    x = x_full.copy()
    y = y_full.copy()
    valid = ~np.isnan(x) & ~np.isnan(y)
    idx = np.where(valid)[0]
    if idx.size < 2:
        return x, y, 0
    max_gap = max(1, int(round(MAX_GAP_S * fps)))
    r = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
    th = np.arctan2(y - cy, x - cx)
    n_filled = 0
    for a, b in zip(idx[:-1], idx[1:]):
        gap = int(b - a - 1)
        if gap <= 0 or gap > max_gap:
            continue
        dth = (th[b] - th[a] + np.pi) % (2 * np.pi) - np.pi  # shortest signed step
        for j in range(1, gap + 1):
            f = j / (gap + 1)
            rj = r[a] + f * (r[b] - r[a])
            tj = th[a] + f * dth
            x[a + j] = cx + rj * np.cos(tj)
            y[a + j] = cy + rj * np.sin(tj)
        n_filled += gap
    return x, y, n_filled


def compute(inp: Inputs, cal: Calibration, x_full, y_full) -> Kinematics:
    common.step_start("step8")
    FPS = inp.fps
    n = inp.n_raw_frames
    t_s = np.arange(n) / FPS

    # Fill short blur-dropout gaps along the orbit before deriving anything, so omega
    # / active-detection / period see a continuous spin. Real-detection coverage in
    # stats.json is unchanged (computed in calibrate, before this).
    x_full, y_full, n_interpolated = _fill_short_gaps(x_full, y_full, cal.cx_px, cal.cy_px, FPS)
    if n_interpolated:
        common.set_validation_flag("interpolated_short_gaps")

    dx = x_full - cal.cx_px
    dy = y_full - cal.cy_px
    r_px = np.sqrt(dx**2 + dy**2)
    r_m = r_px / cal.px_per_m

    theta_raw = np.arctan2(dy, dx)
    theta_unwrapped = _segmented(theta_raw, lambda seg, _m: np.unwrap(seg))

    window = max(11, 2 * (int(FPS) // 6) + 1)
    if window % 2 == 0:
        window += 1
    theta_smooth = _savgol_nan_safe(theta_unwrapped, window, 3)

    # Single omega source for everything downstream. A lone valid frame (an island
    # between tracking gaps) has no defined angular velocity, and np.gradient raises
    # on a <2-point array — return NaN for those so they stay gaps, not a crash.
    def _grad(seg, m):
        if len(seg) < 2:
            return np.full_like(seg, np.nan, dtype=float)
        return np.gradient(seg, t_s[m])
    omega = _segmented(theta_smooth, _grad)
    omega = scipy.ndimage.median_filter(omega, size=max(5, int(FPS // 10)), mode="nearest")

    # ── Active detection (old step 7), now off the same omega ────────────────
    common.step_start("step7")
    omega_max = float(np.nanmax(np.abs(omega)))
    omega_threshold_pct = 0.10 if inp.duration_s >= 10 else 0.20
    omega_threshold = omega_threshold_pct * omega_max
    min_active_frames = max(1, int(max(0.5, 1.0 / omega_threshold_pct / 10) * FPS))
    active_raw = np.abs(omega) > omega_threshold
    active_raw[np.isnan(omega)] = False
    labeled, n_bursts = scipy.ndimage.label(active_raw)
    active_mask = np.zeros(n, dtype=bool)
    for i in range(1, n_bursts + 1):
        burst = labeled == i
        if burst.sum() >= min_active_frames:
            active_mask |= burst
    active_duration_s = float(active_mask.sum()) / FPS
    np.save("analysis_output/data/active_mask.npy", active_mask)
    common.step_end("step7")

    omega_active = omega[active_mask & ~np.isnan(omega)]
    if omega_active.size == 0:
        common.set_validation_flag("no_active_rotation")
        omega_active = omega[~np.isnan(omega)]

    # theta = arctan2(dy, dx) is measured in IMAGE/pixel coordinates, where the row index dy
    # grows DOWNWARD. So an increasing theta (omega > 0) traces right -> bottom -> left -> top on
    # screen — i.e. the object turns CLOCKWISE as the viewer sees it. Convert to the viewer frame
    # HERE (the one sign flip) so every downstream string — the PDF header, the material prose,
    # the video orbit colour — matches what plays on screen (was inverted: called a CW clip "CCW").
    rotation_direction = "CW" if float(np.nanmedian(omega_active)) > 0 else "CCW"

    v_m_s = np.abs(omega) * cal.r_fit_m
    spike = 5.0 * float(np.nanmedian(np.abs(omega_active)))
    omega_for_ac = np.where(np.abs(omega) > spike, np.nan, omega)
    ac_m_s2 = omega_for_ac**2 * cal.r_fit_m
    if np.any(np.abs(omega) > spike):
        common.set_validation_flag("omega_spike")

    k = Kinematics(
        t_s=t_s, r_px=r_px, r_m=r_m, theta_unwrapped=theta_unwrapped,
        omega=omega, v_m_s=v_m_s, ac_m_s2=ac_m_s2, active_mask=active_mask,
        rotation_direction=rotation_direction, active_duration_s=active_duration_s,
        x_px=x_full, y_px=y_full, n_interpolated=n_interpolated,
    )

    active_idx = np.where(active_mask)[0]
    if active_idx.size:
        k.active_start_s = float(t_s[active_idx[0]])
        k.active_end_s = float(t_s[active_idx[-1]])

    am = active_mask & ~np.isnan(omega)
    k.mean_r_m = float(np.nanmean(r_m[active_mask])) if active_mask.any() else 0.0
    k.std_r_m = float(np.nanstd(r_m[active_mask])) if active_mask.any() else 0.0
    k.mean_omega = float(np.nanmean(omega[am])) if am.any() else 0.0
    k.std_omega = float(np.nanstd(omega[am])) if am.any() else 0.0
    k.mean_v = float(np.nanmean(v_m_s[active_mask])) if active_mask.any() else 0.0
    k.mean_ac = float(np.nanmean(ac_m_s2[active_mask])) if active_mask.any() else 0.0
    k.max_ac = float(np.nanmax(ac_m_s2[active_mask])) if active_mask.any() else 0.0
    if k.mean_r_m and k.std_r_m / max(k.mean_r_m, 1e-9) > 0.30:
        common.set_validation_flag("radius_unstable")

    _motion_model(k, cal, FPS)
    _period(k, inp, FPS)
    _phases(k, inp, FPS, theta_smooth)
    # Surface the spin-up/down endpoints from the (robust) motion model when the
    # flicker-prone per-frame phase labeller left them empty.
    if k.motion_type == "accelerating" and k.increase_start_omega is None:
        k.increase_start_omega = k.omega_initial
        k.increase_end_omega = k.omega_final
    elif k.motion_type == "decelerating" and k.decrease_end_omega is None:
        k.decrease_end_omega = k.omega_final
    common.step_end("step8")
    return k


def _motion_model(k: Kinematics, cal: Calibration, FPS: float) -> None:
    """Classify the rotation as uniform vs (de)accelerating from a constant-alpha
    fit. We fit theta(t) over the longest active run to a quadratic — theta is the
    *integral* of omega, so the fit is smooth and noise-insensitive, unlike
    thresholding omega's derivative (which flickers and was why an obvious fan
    spin-up was mislabelled STABLE). A non-uniform classification gates the
    period_mismatch / unstable_phase_linearity flags, which a single-omega model
    raises spuriously on motion that is genuinely changing speed."""
    n = len(k.t_s)
    runs, s = [], None
    for i in range(n):
        if k.active_mask[i] and s is None:
            s = i
        elif not k.active_mask[i] and s is not None:
            runs.append((s, i)); s = None
    if s is not None:
        runs.append((s, n))
    if not runs:
        return
    a, b = max(runs, key=lambda r: r[1] - r[0])

    # A constant-alpha fit assumes omega is monotonic across the window. If instead omega
    # RISES then FALLS inside the run — a flick: the object is nudged up to a peak, then
    # coasts down — a single quadratic over the whole run mixes the two and its intercept
    # invents an initial omega that never occurred (red phone: fit says 9.93 rad/s at the
    # window start where the data reads 2.69, because the parabola splits the difference over
    # rise+fall). Detect that, and fit only the dominant monotonic side (the coast-down),
    # so omega_initial is the true peak. Monotonic accel/decel and uniform clips keep the
    # whole-run fit unchanged: the peak sits at an END, so no interior split is triggered.
    seg_a, seg_b, impulsive = a, b, False
    w_run = np.abs(k.omega[a:b])
    if np.isfinite(w_run).any():
        pk = a + int(np.nanargmax(w_run))
        w_peak = float(np.nanmax(w_run))
        edge = max(1, int(FPS * 0.1))
        w_start = float(np.nanmedian(np.abs(k.omega[a:min(a + edge, b)])))
        w_end = float(np.nanmedian(np.abs(k.omega[max(b - edge, a):b])))
        climb = w_peak - (w_start if np.isfinite(w_start) else w_peak)
        drop = w_peak - (w_end if np.isfinite(w_end) else w_peak)
        # Interior peak with a real climb AND a real drop (both > 30% of the peak) = a flick.
        if a < pk < b - 1 and w_peak > 0 and climb > 0.3 * w_peak and drop > 0.3 * w_peak:
            impulsive = True
            # Fit the longer monotonic side — almost always the coast-down [peak, end].
            seg_a, seg_b = (a, pk + 1) if (pk - a) >= (b - pk) else (pk, b)
    k.impulsive_start = impulsive

    m = np.zeros(n, dtype=bool); m[seg_a:seg_b] = True
    m &= ~np.isnan(k.theta_unwrapped)
    t, th = k.t_s[m], k.theta_unwrapped[m]
    dur = float(t[-1] - t[0]) if t.size else 0.0
    # The span alpha is actually fit over — the material must divide Delta-omega by THIS,
    # not the whole-clip duration (dividing by 5.84 s instead of the ~1.6 s coast-down is
    # what printed alpha = -4.07 from an expression that evaluates to -1.34).
    k.fit_window_s = dur
    if t.size < 10 or dur < 1.0:
        return  # too little to fit a curvature

    c_lin = np.polyfit(t, th, 1)
    c_quad = np.polyfit(t, th, 2)
    var_lin = float(((th - np.polyval(c_lin, t)) ** 2).mean())
    var_quad = float(((th - np.polyval(c_quad, t)) ** 2).mean())
    var_th = float(th.var())
    resid_drop = 1.0 - var_quad / max(var_lin, 1e-12)
    alpha = float(2.0 * c_quad[0])
    omega_t = np.polyval(np.polyder(c_quad), t)
    mean_w = float(np.abs(omega_t).mean())
    dw_ratio = abs(alpha) * dur / max(mean_w, 1e-6)

    k.alpha_rad_s2 = alpha
    k.alpha_r2 = 1.0 - var_quad / max(var_th, 1e-12)
    k.omega_initial = float(omega_t[0])
    k.omega_final = float(omega_t[-1])

    # Non-uniform only when the quadratic clearly beats the line AND omega actually
    # changes appreciably across the window. Both guards must hold so noise on a
    # genuinely steady spin does not get read as acceleration.
    if resid_drop > 0.7 and dw_ratio > 0.3:
        k.motion_type = "accelerating" if alpha > 0 else "decelerating"
        # SIGNED: a_t = alpha * r. In a deceleration the sign IS the physics — a_t points
        # against the motion — so keep alpha's sign rather than storing a bare magnitude.
        k.a_t_mean_m_s2 = alpha * cal.r_fit_m
    else:
        k.motion_type = "uniform"


def _period(k: Kinematics, inp: Inputs, FPS: float) -> None:
    omega_active = k.omega[k.active_mask & ~np.isnan(k.omega)]
    med = float(np.nanmedian(np.abs(omega_active))) if omega_active.size else 0.0
    k.T_primary = float(2 * np.pi / med) if med > 0 else 0.0
    k.frequency_hz = 1.0 / k.T_primary if k.T_primary > 0 else 0.0
    k.period_s = k.T_primary

    # Longest contiguous active run, in seconds.
    runs, cur = [], 0
    for a in k.active_mask:
        cur = cur + 1 if a else 0
        if not a and cur:
            runs.append(cur)
    if cur:
        runs.append(cur)
    longest_s = float(max(runs, default=0)) / FPS

    if longest_s < 3 * max(k.T_primary, 1e-9):
        common.set_validation_flag("fft_skipped_insufficient_data")
        k.T_fft = k.T_primary
    else:
        k.T_fft = _fft_period(k, FPS) or k.T_primary

    k.period_discrepancy = (abs(k.T_primary - k.T_fft) / k.T_primary) if k.T_primary > 0 else 0.0
    # A (de)accelerating spin has no single period, so T_primary (instantaneous,
    # from the median omega) and T_fft legitimately disagree — don't flag it.
    if k.period_discrepancy > 0.05 and k.motion_type == "uniform":
        common.set_validation_flag("period_mismatch")


def _fft_period(k: Kinematics, FPS: float) -> float | None:
    theta = k.theta_unwrapped[k.active_mask]
    t = k.t_s[k.active_mask]
    valid = ~np.isnan(theta)
    if valid.sum() < 4:
        return None
    labeled, nseg = scipy.ndimage.label(valid)
    segs = []
    for i in range(1, nseg + 1):
        m = labeled == i
        st, sa = t[m], theta[m]
        segs.append(sa - np.mean(sa))
    if not segs or len(segs[0]) < 4:
        return None
    detr = np.concatenate(segs)
    dt = 1.0 / FPS
    fft_vals = np.abs(np.fft.rfft(detr))[1:]
    fft_freqs = np.fft.rfftfreq(len(detr), dt)[1:]
    if fft_freqs.size == 0:
        return None
    peak = float(fft_freqs[int(np.argmax(fft_vals))])
    return 1.0 / peak if peak > 0 else None


def _phase_runs(labels, n):
    """Contiguous (start, end, label) runs over the label array."""
    out, i = [], 0
    while i < n:
        j = i
        while j < n and labels[j] == labels[i]:
            j += 1
        out.append((i, j, labels[i]))
        i = j
    return out


def _despeckle_phases(labels, min_phase, n) -> None:
    """Clean raw per-frame labels into whole phases: (1) close short STABLE gaps flanked by the
    SAME direction (gradient noise briefly dipping under threshold mid-phase), then (2) despeckle
    any non-STABLE run shorter than min_phase to STABLE. Mutates `labels` in place."""
    rs = _phase_runs(labels, n)
    for idx, (a, b, lab) in enumerate(rs):
        if lab == "STABLE" and (b - a) < min_phase and 0 < idx < len(rs) - 1:
            prv, nxt = rs[idx - 1][2], rs[idx + 1][2]
            if prv == nxt and prv in ("INCREASE", "DECREASE"):
                labels[a:b] = prv
    for a, b, lab in _phase_runs(labels, n):
        if lab in ("INCREASE", "DECREASE") and (b - a) < min_phase:
            labels[a:b] = "STABLE"


def _merge_same_direction(labels, speed_smoothed, rest_level, n) -> None:
    """A frequency-synth staircase (and a stepwise real spin-up) reads as many short same-direction
    runs split by stable treads. Merge two same-direction runs — and the STABLE treads between them
    — into one coarse phase, so a spin-up is ONE INCREASE not a dozen step-edges. Do NOT merge
    across a gap that dips toward rest: that marks a genuinely separate spin-down event (repeated
    impulses, e.g. a hand re-spinning a wheel). Mutates `labels` in place."""
    changed = True
    while changed:
        changed = False
        rs = _phase_runs(labels, n)
        for i in range(len(rs)):
            a, b, lab = rs[i]
            if lab not in ("INCREASE", "DECREASE"):
                continue
            j = i + 1
            while j < len(rs) and rs[j][2] == "STABLE":
                j += 1
            if j >= len(rs) or rs[j][2] != lab:
                continue
            gap_lo, gap_hi = b, rs[j][0]
            gap_min = (float(np.nanmin(np.abs(speed_smoothed[gap_lo:gap_hi])))
                       if gap_hi > gap_lo else rest_level + 1.0)
            if gap_min < rest_level:
                continue
            labels[a:rs[j][1]] = lab
            changed = True
            break


def _phases(k: Kinematics, inp: Inputs, FPS: float, theta_smooth) -> None:
    n = inp.n_raw_frames
    min_phase = max(1, int(0.5 * FPS))
    if k.motion_type == "uniform":
        # A uniform clip has, by definition, no speeding/slowing phase — the single-regime
        # angular-acceleration fit already found alpha ~ 0. Label every active frame STABLE so
        # tracking jitter on a steady spin cannot sprout a spurious INCREASE/DECREASE band.
        labels = np.where(k.active_mask, "STABLE", "INACTIVE").astype(object)
    else:
        # Label on SPEED |ω| (rotation-direction-invariant): "speeding up / slowing down" is about
        # how fast it spins, not the sign of ω. Labelling signed ω inverts every clockwise clip,
        # mislabelling a spin-up as "slowing down".
        speed = np.abs(k.omega)
        smoothed = scipy.ndimage.median_filter(speed, size=max(5, int(FPS * 0.5)), mode="nearest")
        # A longer trend window (~1.2 s) erases 1/rev projection ripples and frequency-synth
        # staircase step-edges, so the gradient reflects only the coarse spin-up / coast-down.
        trend = scipy.ndimage.uniform_filter1d(smoothed, size=max(5, int(1.2 * FPS)), mode="nearest")
        domega = _segmented(trend, lambda seg, m: np.gradient(seg, k.t_s[m]))
        # Threshold off the 90th percentile of |dω/dt| over ACTIVE frames, NOT its max: an impulsive
        # flick's near-vertical rise spike dominates the max, lifting the threshold so high the
        # genuine coast-down falls under it. Floor it to a fraction of the ω dynamic range per unit
        # time so a real phase must change speed by a meaningful amount, not by tracking jitter on a
        # near-uniform spin.
        absd = np.abs(domega)
        active_absd = absd[k.active_mask & np.isfinite(absd)]
        base = float(np.percentile(active_absd, 90)) if active_absd.size else 0.0
        oact = np.abs(k.omega[k.active_mask & ~np.isnan(k.omega)])
        orange = float(np.percentile(oact, 95) - np.percentile(oact, 5)) if oact.size else 0.0
        omed = float(np.nanmedian(oact)) if oact.size else 0.0
        dur = max(k.active_mask.sum() / FPS, 1e-6)
        thr = max(0.10 * base, 0.06 * orange / dur)

        labels = np.full(n, "INACTIVE", dtype=object)
        for i in range(n):
            if not k.active_mask[i]:
                continue
            d = domega[i]
            labels[i] = ("INCREASE" if d > thr else "DECREASE" if d < -thr else "STABLE") \
                if np.isfinite(d) else "STABLE"
        _despeckle_phases(labels, min_phase, n)
        # Merge staircase steps into coarse phases BEFORE the net-change filter, so a spin-up's
        # steps sum into one band (rather than each step being filtered away individually).
        _merge_same_direction(labels, smoothed, 0.30 * omed, n)
        # Net-change filter (post-merge): drop a phase whose net |Δω| is a small fraction of the
        # typical spin speed — a ripple crest / wobble, not a real acceleration. Median-normalised so
        # a small oscillation on a fast steady spin is suppressed while a real burst survives.
        for a, b, lab in _phase_runs(labels, n):
            if lab in ("INCREASE", "DECREASE") and (
                    omed <= 0 or abs(float(trend[b - 1] - trend[a])) < 0.30 * omed):
                labels[a:b] = "STABLE"
        _despeckle_phases(labels, min_phase, n)

    stable_mask = labels == "STABLE"
    segments, inseg, s0 = [], False, 0
    for i in range(n):
        if stable_mask[i] and not inseg:
            inseg, s0 = True, i
        elif not stable_mask[i] and inseg:
            inseg = False
            segments.append((s0, i))
    if inseg:
        segments.append((s0, n))

    slopes, weights, r2s, errs = [], [], [], []
    for a, b in segments:
        m = np.zeros(n, dtype=bool)
        m[a:b] = True
        sel = m & ~np.isnan(k.theta_unwrapped)
        if sel.sum() < 2:
            continue
        slope, _i, r2, _p, err = scipy.stats.linregress(k.t_s[sel], k.theta_unwrapped[sel])
        # A linear theta fit is only expected to hold for uniform rotation; under a
        # constant-alpha spin theta is quadratic, so a sub-0.99 linear R^2 is the
        # modelled behaviour, not an instability.
        if r2 < 0.99 and k.motion_type == "uniform":
            common.set_validation_flag("unstable_phase_linearity")
        slopes.append(float(slope)); weights.append(float(sel.sum()))
        r2s.append(float(r2)); errs.append(float(err))

    stable_ac_mask = np.zeros(n, dtype=bool)
    for a, b in segments:
        stable_ac_mask[a:b] = True

    if not slopes or stable_mask.sum() < FPS * 0.5:
        common.set_validation_flag("no_stable_phase_detected")
        oa = k.omega[k.active_mask & ~np.isnan(k.omega)]
        k.stable_mean_omega = float(np.nanmedian(np.abs(oa))) if oa.size else 0.0
        k.stable_omega_r2 = float("nan")
        k.stable_omega_std_err = float("nan")
    else:
        w = np.array(weights)
        k.stable_mean_omega = float(abs(np.average(slopes, weights=w)))
        k.stable_omega_r2 = float(np.average(r2s, weights=w))
        k.stable_omega_std_err = float(np.average(errs, weights=w))
    k.stable_mean_ac = (float(np.nanmean(k.ac_m_s2[stable_ac_mask]))
                        if stable_ac_mask.any() else k.mean_ac)
    k.n_stable_segments = len(segments)
    k.stable_segments = [[int(a), int(b)] for a, b in segments]
    k.phase_labels = labels.tolist()

    # Phase-boundary omega samples.
    inc_start = inc_end = dec_end = None
    i = 0
    while i < n:
        p = labels[i]
        j = i
        while j < n and labels[j] == p:
            j += 1
        if p == "INCREASE":
            if inc_start is None:
                for x in range(i, j):
                    if not np.isnan(k.omega[x]):
                        inc_start = float(k.omega[x]); break
            for x in range(j - 1, i - 1, -1):
                if not np.isnan(k.omega[x]):
                    inc_end = float(k.omega[x]); break
        elif p == "DECREASE":
            for x in range(j - 1, i - 1, -1):
                if not np.isnan(k.omega[x]):
                    dec_end = float(k.omega[x]); break
        i = j
    k.increase_start_omega = inc_start
    k.increase_end_omega = inc_end
    k.decrease_end_omega = dec_end
