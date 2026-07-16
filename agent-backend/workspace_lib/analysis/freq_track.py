"""Frequency (blade-pass) analysis — recover rotation rate without tracking a point.

For a fast, multi-bladed rotor (e.g. a ceiling fan at speed) two things defeat
point-tracking at once:
  - the blades are **identical**, so an appearance tracker (SAM3) cannot tell them
    apart and aliases / hops between them (wagon-wheel effect);
  - the long exposure **motion-blurs** any marker into a faint streak, so colour
    tracking finds no concentrated blob either.

Neither is cured by a higher frame rate — blur is set by shutter, and the identical
blades alias regardless. But the rotation is still strongly *periodic*: sample image
intensity at fixed points on a ring around the hub and each blade sweeping past makes
the intensity dip. The dominant frequency of that signal is the **blade-pass
frequency** `f_b`; with `N` blades the rotation frequency is `f_rot = f_b / N` and
`omega = 2*pi*f_rot`. Probes all around the ring agree on `f_b`, which is the
confidence check.

Output is a measured `omega` (constant over the window). To feed the rest of the
frozen pipeline unchanged, `synth_trajectory` builds a clean orbit at that `omega`
and a calibrated `orbit_radius_px`, in the remote-/track schema, so calibration /
kinematics / figures run as usual. The synthetic nature is recorded in
`frequency_meta.json` and flagged downstream — the *rate* is measured, the per-frame
point is reconstructed (a fast blurred rotor has no resolvable point to report).

Nyquist: `f_b` must be below `fps/2`. A 5-blade fan at ~0.5 rev/s gives `f_b≈2.7 Hz`,
fine at 30/60 fps; a fast fan needs 60 fps to keep `f_b` resolved.
"""
from __future__ import annotations

import argparse
import json
import math

import cv2
import numpy as np


def _peak_hz_parabolic(sp: np.ndarray, freqs: np.ndarray, band: np.ndarray) -> float:
    """Sub-bin frequency of the spectral peak inside ``band``.

    Taking the raw ``argmax`` bin quantises the recovered frequency to the FFT bin
    spacing Δf = fps/window (≈0.4 Hz for a 2.5 s window). On the blade-pass line that
    surfaces as a non-physical STAIRCASE in ω(t): steps of 2π·Δf/n_blades (≈0.5 rad/s
    for a 5-blade fan), which reads as the fan holding constant speed then jumping — a
    real rotor never does that. A 3-point parabolic fit around the peak recovers the
    true sub-bin location, so a smoothly-varying rotor comes out smooth. Falls back to
    the bin centre at a band edge or a degenerate (flat/reversed) parabola.
    """
    band_idx = np.flatnonzero(band)
    if band_idx.size == 0:
        return 0.0
    k = int(band_idx[np.argmax(sp[band])])          # absolute peak-bin index
    if k <= 0 or k >= sp.size - 1:
        return float(freqs[k])
    a, b, c = float(sp[k - 1]), float(sp[k]), float(sp[k + 1])
    denom = a - 2.0 * b + c
    if denom == 0.0:
        return float(freqs[k])
    delta = 0.5 * (a - c) / denom                    # in (-0.5, 0.5) for a true peak
    if not -0.5 <= delta <= 0.5:
        return float(freqs[k])
    df = float(freqs[1] - freqs[0])
    return float(freqs[k] + delta * df)


def analyze(
    video_path: str,
    hub_px,
    ring_radius_px: float,
    n_blades: int,
    n_probes: int = 12,
    fmin: float = 0.5,
    fmax: float = None,
) -> dict:
    """Measure blade-pass frequency from intensity on a ring of probe points.

    Returns a dict with the per-probe peaks (agreement = confidence), the median
    blade-pass frequency, and the derived rotation rate / omega / period.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"could not open video: {video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    cxh, cyh = float(hub_px[0]), float(hub_px[1])
    angs = np.linspace(0, 2 * math.pi, n_probes, endpoint=False)
    pts = [(int(cxh + ring_radius_px * math.cos(a)), int(cyh + ring_radius_px * math.sin(a)))
           for a in angs]
    series = [[] for _ in pts]
    nb = 0
    fw = fh = None
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
        h, w = g.shape
        fw, fh = w, h
        for k, (x, y) in enumerate(pts):
            x0, x1 = max(0, x - 3), min(w, x + 4)
            y0, y1 = max(0, y - 3), min(h, y + 4)
            series[k].append(float(g[y0:y1, x0:x1].mean()) if x1 > x0 and y1 > y0 else 0.0)
        nb += 1
    cap.release()
    series = np.asarray(series)
    if nb < 16 or fps <= 0:
        raise RuntimeError(f"too few frames / bad fps for frequency analysis (nb={nb}, fps={fps})")
    if fmax is None:
        fmax = fps / 2.0
    freqs = np.fft.rfftfreq(nb, 1.0 / fps)
    band = (freqs >= fmin) & (freqs < fmax)
    if not band.any():
        raise RuntimeError("empty analysis band — check fmin/fmax vs fps")
    win = np.hanning(nb)
    peaks = []
    stack = np.zeros(int(band.sum()))
    for k in range(len(pts)):
        s = series[k] - series[k].mean()
        sp = np.abs(np.fft.rfft(s * win))
        peaks.append(_peak_hz_parabolic(sp, freqs, band))
        stack += sp[band]
    peaks = np.asarray(peaks)
    f_b = float(np.median(peaks))
    stack_full = np.zeros_like(freqs); stack_full[band] = stack   # back onto full grid
    f_b_stack = _peak_hz_parabolic(stack_full, freqs, band)
    spread = float(np.std(peaks))                       # Hz agreement across probes
    f_rot = f_b / max(1, n_blades)
    omega = 2 * math.pi * f_rot
    # rotation sense: phase of f_b across angularly-ordered probes (sign of slope)
    direction = _direction(series, win, freqs, f_b, angs)
    return {
        "fps": fps,
        "n_frames": nb,
        "frame_w": fw,
        "frame_h": fh,
        "ring_radius_px": float(ring_radius_px),
        "hub_px": [cxh, cyh],
        "n_blades": int(n_blades),
        "n_probes": int(n_probes),
        "per_probe_blade_pass_hz": [round(p, 3) for p in peaks.tolist()],
        "blade_pass_hz": round(f_b, 4),
        "blade_pass_hz_stacked": round(f_b_stack, 4),
        "probe_spread_hz": round(spread, 4),
        "rotation_hz": round(f_rot, 4),
        "omega_rad_s": round(omega, 4),
        "period_s": round(1.0 / f_rot, 4) if f_rot > 0 else None,
        "rpm": round(f_rot * 60.0, 2),
        "direction": direction,
        "method": "frequency_blade_pass",
    }


def _probe_series(video_path, hub_px, ring_radius_px, n_probes):
    """Sample grayscale intensity at a ring of probe points for every frame."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"could not open video: {video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    cxh, cyh = float(hub_px[0]), float(hub_px[1])
    angs = np.linspace(0, 2 * math.pi, n_probes, endpoint=False)
    fw = fh = None
    rows = []
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
        fh, fw = g.shape
        vals = []
        for a in angs:
            x = int(cxh + ring_radius_px * math.cos(a)); y = int(cyh + ring_radius_px * math.sin(a))
            x0, x1 = max(0, x - 3), min(fw, x + 4); y0, y1 = max(0, y - 3), min(fh, y + 4)
            vals.append(float(g[y0:y1, x0:x1].mean()) if x1 > x0 and y1 > y0 else 0.0)
        rows.append(vals)
    cap.release()
    return np.asarray(rows).T, fps, fw, fh, angs  # series: n_probes x N


def analyze_windowed(video_path, hub_px, ring_radius_px, n_blades, n_probes=12,
                     window_s=2.0, hop_s=0.5, fmin=0.5, fmax=None) -> dict:
    """Time-resolved ω(t): blade-pass FFT on a sliding window. Captures spin-up /
    spin-down over the whole clip (a single global FFT would smear a varying rate)."""
    series, fps, fw, fh, angs = _probe_series(video_path, hub_px, ring_radius_px, n_probes)
    n = series.shape[1]
    if n < 16 or fps <= 0:
        raise RuntimeError(f"too few frames / bad fps (n={n}, fps={fps})")
    if fmax is None:
        fmax = fps / 2.0
    wlen = max(16, int(round(window_s * fps)))
    hop = max(1, int(round(hop_s * fps)))
    omega_t = []  # (t_center_s, omega_rad_s, blade_pass_hz, spread_hz)
    starts = list(range(0, max(1, n - wlen + 1), hop))
    for s0 in starts:
        seg = series[:, s0:s0 + wlen]
        if seg.shape[1] < wlen:
            break
        freqs = np.fft.rfftfreq(wlen, 1.0 / fps)
        band = (freqs >= fmin) & (freqs < fmax)
        if not band.any():
            continue
        win = np.hanning(wlen)
        peaks = []
        for k in range(seg.shape[0]):
            s = seg[k] - seg[k].mean()
            sp = np.abs(np.fft.rfft(s * win))
            peaks.append(_peak_hz_parabolic(sp, freqs, band))
        peaks = np.asarray(peaks)
        f_b = float(np.median(peaks))
        t_c = (s0 + wlen / 2) / fps
        omega_t.append((round(t_c, 4), round(2 * math.pi * (f_b / n_blades), 4),
                        round(f_b, 4), round(float(np.std(peaks)), 4)))
    # global direction from the whole series
    freqs_g = np.fft.rfftfreq(n, 1.0 / fps)
    f_b_g = float(np.median([o[2] for o in omega_t])) if omega_t else 0.0
    direction = _direction(series, np.hanning(n), freqs_g, f_b_g, angs)
    return {
        "fps": fps, "n_frames": n, "frame_w": fw, "frame_h": fh,
        "ring_radius_px": float(ring_radius_px), "hub_px": [float(hub_px[0]), float(hub_px[1])],
        "n_blades": int(n_blades), "n_probes": int(n_probes),
        "window_s": window_s, "hop_s": hop_s,
        "omega_t": omega_t,                       # [(t, omega, blade_pass_hz, spread)]
        "omega_min": round(min(o[1] for o in omega_t), 4) if omega_t else None,
        "omega_max": round(max(o[1] for o in omega_t), 4) if omega_t else None,
        "direction": direction,
        "method": "frequency_blade_pass_windowed",
    }


def synth_trajectory_varomega(meas_w: dict, orbit_radius_px: float, label: str, phase0=0.0) -> dict:
    """Build an orbit whose instantaneous ω follows the windowed ω(t) (per-frame
    interpolated, integrated to θ). Reproduces spin-up/down through the frozen kinematics."""
    fps = meas_w["fps"]; n = meas_w["n_frames"]
    cx, cy = meas_w["hub_px"]
    sign = 1.0 if meas_w.get("direction", "CCW") == "CCW" else -1.0
    ts = np.array([o[0] for o in meas_w["omega_t"]])
    ws = np.array([o[1] for o in meas_w["omega_t"]]) * sign
    frame_t = np.arange(n) / fps
    omega_f = np.interp(frame_t, ts, ws)          # per-frame ω (flat-extrapolated at ends)
    theta = phase0 + np.cumsum(omega_f) / fps      # ∫ω dt
    half = orbit_radius_px / 2.0
    traj = []
    for i in range(n):
        x = cx + orbit_radius_px * math.cos(theta[i]); y = cy + orbit_radius_px * math.sin(theta[i])
        traj.append({"frame": i, "cx": x, "cy": y, "bbox": [x - half, y - half, x + half, y + half]})
    return {
        "status": "success", "trajectories": {label: traj},
        "video_info": {"width": meas_w.get("frame_w"), "height": meas_w.get("frame_h"),
                       "rotation": 0, "nb_frames": n, "fps": fps},
        "track_coverage": 1.0, "method": "frequency_synth_windowed",
    }


def _direction(series, win, freqs, f_b, angs) -> str:
    """CCW/CW from the phase gradient of the blade-pass component around the ring."""
    bin_i = int(np.argmin(np.abs(freqs - f_b)))
    phases = []
    for k in range(len(series)):
        s = series[k] - series[k].mean()
        phases.append(np.angle(np.fft.rfft(s * win)[bin_i]))
    ph = np.unwrap(np.asarray(phases))
    slope = np.polyfit(angs, ph, 1)[0]
    return "CCW" if slope >= 0 else "CW"


def synth_trajectory(meas: dict, orbit_radius_px: float, label: str, phase0: float = 0.0) -> dict:
    """Build a clean orbit at the measured omega + given radius (remote-/track schema)."""
    fps = meas["fps"]
    n = meas["n_frames"]
    cx, cy = meas["hub_px"]
    omega = meas["omega_rad_s"] * (1.0 if meas.get("direction", "CCW") == "CCW" else -1.0)
    # bbox side == orbit_radius_px so the generic reference-sizing step (median bbox
    # (W+H)/2) recovers diameter_px = orbit_radius_px. Pair it with a sidecar
    # physical_size = orbit radius in metres and px_per_m comes out correct, and the
    # synthesized point's mean_r equals that orbit radius — internally consistent.
    half = orbit_radius_px / 2.0
    traj = []
    for i in range(n):
        th = phase0 + omega * (i / fps)
        x = cx + orbit_radius_px * math.cos(th)
        y = cy + orbit_radius_px * math.sin(th)
        traj.append({"frame": i, "cx": x, "cy": y,
                     "bbox": [x - half, y - half, x + half, y + half]})
    return {
        "status": "success",
        "trajectories": {label: traj},
        "video_info": {"width": meas.get("frame_w"), "height": meas.get("frame_h"),
                       "rotation": 0, "nb_frames": n, "fps": fps},
        "track_coverage": 1.0,
        "method": "frequency_synth",
    }


def _main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Blade-pass frequency analysis → omega (+ synthetic orbit).")
    ap.add_argument("--video", required=True)
    ap.add_argument("--hub", required=True, help="cx,cy px of rotation centre")
    ap.add_argument("--ring-radius", type=float, required=True, help="probe-ring radius px (within the disc)")
    ap.add_argument("--n-blades", type=int, required=True)
    ap.add_argument("--n-probes", type=int, default=12)
    ap.add_argument("--fmin", type=float, default=0.5)
    ap.add_argument("--fmax", type=float, default=None)
    ap.add_argument("--label", default="rotor", help="trajectory key for the synthesized orbit")
    ap.add_argument("--orbit-radius", type=float, default=None,
                    help="orbit radius px for the synthesized point (default: ring radius, flagged estimate)")
    ap.add_argument("--window-s", type=float, default=None,
                    help="enable TIME-RESOLVED ω(t): sliding-window length (s). For full clips with varying speed.")
    ap.add_argument("--hop-s", type=float, default=0.5, help="window hop (s) for ω(t) mode")
    ap.add_argument("--out", default=None, help="write api_cache.json here (synthetic orbit)")
    ap.add_argument("--meta-out", default=None, help="write frequency_meta.json here (the measurement)")
    a = ap.parse_args(argv)
    hub = [float(x) for x in a.hub.split(",")]
    orbit_r = a.orbit_radius if a.orbit_radius is not None else a.ring_radius
    if a.window_s:
        meas = analyze_windowed(a.video, hub, a.ring_radius, a.n_blades, a.n_probes,
                                a.window_s, a.hop_s, a.fmin, a.fmax)
        meas["orbit_radius_px"] = float(orbit_r)
        meas["orbit_radius_source"] = "sidecar" if a.orbit_radius is not None else "ring_radius_estimate"
        print(f"[freq_track] WINDOWED ω(t): {len(meas['omega_t'])} windows, "
              f"ω {meas['omega_min']}→{meas['omega_max']} rad/s, {meas['direction']}, "
              f"win={a.window_s}s hop={a.hop_s}s")
        if a.meta_out:
            with open(a.meta_out, "w") as f:
                json.dump(meas, f, indent=2)
            print(f"[freq_track] measurement → {a.meta_out}")
        if a.out:
            with open(a.out, "w") as f:
                json.dump(synth_trajectory_varomega(meas, orbit_r, a.label), f)
            print(f"[freq_track] time-varying synthetic orbit (r={orbit_r:.0f}px) → {a.out}")
        return 0
    meas = analyze(a.video, hub, a.ring_radius, a.n_blades, a.n_probes, a.fmin, a.fmax)
    meas["orbit_radius_px"] = float(orbit_r)
    meas["orbit_radius_source"] = "sidecar" if a.orbit_radius is not None else "ring_radius_estimate"
    print(f"[freq_track] blade_pass={meas['blade_pass_hz']}Hz spread={meas['probe_spread_hz']}Hz "
          f"-> {meas['rpm']} RPM, omega={meas['omega_rad_s']} rad/s, T={meas['period_s']}s, {meas['direction']}")
    if a.meta_out:
        with open(a.meta_out, "w") as f:
            json.dump(meas, f, indent=2)
        print(f"[freq_track] measurement → {a.meta_out}")
    if a.out:
        cache = synth_trajectory(meas, orbit_r, a.label)
        with open(a.out, "w") as f:
            json.dump(cache, f)
        print(f"[freq_track] synthetic orbit (r={orbit_r:.0f}px) → {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
