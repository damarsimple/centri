"""Seeded, deterministic figure generator (run, don't re-author).

The figures subagent used to write all of this matplotlib by hand each job, which
reintroduced two recurring bugs: plotting trajectory geometry from the raw
full-frame `api_cache.json` (circle floats `roi_crop.y_off` px off the points) and
copying hardcoded example numbers from the prompt. Both are structural, not
aesthetic — so the plotting is frozen here and the subagent's job relaxes to
"run this, look at the output, only patch if a panel genuinely looks wrong."

Reads `analysis_output/data/{stats.json,kinematics.csv}` and the cropped video,
writes the 9 standard plots + `summary_panel.png` into `analysis_output/plots/`,
plus `figure_qa.json` (the provenance the deterministic `verify_figures` gate
checks). Everything is in CROPPED-video space, read from `kinematics.csv`
(`x_px,y_px`) — the same space as `stats["calibration"]["cx_px","cy_px"]` — so the
centre, the fitted circle and the points always coincide.

    python -m analysis.render.figures
"""
from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

DATA = Path("analysis_output/data")
PLOTS = Path("analysis_output/plots")
ROI = Path("analysis_output/roi")

STYLE = {
    "figure.dpi": 150,
    "savefig.dpi": 150,
    "font.family": "serif",
    "axes.grid": True,
    "grid.linestyle": "--",
    "grid.alpha": 0.4,
}
PHASE_COLOURS = {
    "STABLE": "#4CAF50",
    "INCREASE": "#FF9800",
    "DECREASE": "#F44336",
    "INACTIVE": "#9E9E9E",
    "IDLE": "#9E9E9E",
}
TRACE = {  # per-series colour
    "omega": "#FB8C00",
    "ac": "#E53935",
    "r": "#1E88E5",
    "theta": "#8E24AA",
    "v": "#00897B",
}


# ── loading ──────────────────────────────────────────────────────────────────

def _load_csv() -> dict[str, np.ndarray]:
    """kinematics.csv → {column: float array} with NaN for blank cells."""
    cols: dict[str, list] = {}
    with (DATA / "kinematics.csv").open() as f:
        reader = csv.DictReader(f)
        names = reader.fieldnames or []
        for n in names:
            cols[n] = []
        for row in reader:
            for n in names:
                v = row.get(n, "")
                if v == "" or v is None:
                    cols[n].append(np.nan)
                else:
                    try:
                        cols[n].append(float(v))
                    except ValueError:
                        cols[n].append(np.nan)
    return {n: np.asarray(v, dtype=float) for n, v in cols.items()}


def _fmt(x, prec=2, unit=""):
    """Human number for a label; '—' when missing (never 'None'/'nan')."""
    if x is None:
        return "—"
    try:
        xf = float(x)
    except (TypeError, ValueError):
        return "—"
    if np.isnan(xf) or np.isinf(xf):
        return "—"
    s = f"{xf:.{prec}f}"
    return f"{s} {unit}".strip() if unit else s


def _title(scene: str, what: str) -> str:
    return f"{what} — {scene}" if scene else what


def _phase_spans(labels: list[str]):
    """Contiguous (start_idx, end_idx, LABEL) runs from per-frame phase labels."""
    spans = []
    if not labels:
        return spans
    start, cur = 0, labels[0]
    for i in range(1, len(labels)):
        if labels[i] != cur:
            spans.append((start, i, cur))
            start, cur = i, labels[i]
    spans.append((start, len(labels), cur))
    return spans


def _shade_phases(ax, t, labels):
    for s, e, lab in _phase_spans(labels):
        c = PHASE_COLOURS.get(str(lab).upper())
        if c and e > s and s < len(t):
            ax.axvspan(t[s], t[min(e, len(t)) - 1], color=c, alpha=0.12, lw=0)


# ── individual figures ───────────────────────────────────────────────────────

def _cropped_video() -> Path | None:
    p = ROI / "cropped.mp4"
    if p.exists():
        return p
    hits = sorted(ROI.glob("cropped*.mp4"))
    return hits[-1] if hits else None


def _first_frame():
    """RGB array of the first cropped frame, or None. Extracts to first_frame.jpg
    once (the basic variant reuses the file rather than re-running ffmpeg)."""
    tmp = PLOTS / "first_frame.jpg"
    if not tmp.exists():
        vid = _cropped_video()
        if vid is not None:
            subprocess.run(["ffmpeg", "-y", "-i", str(vid), "-vframes", "1",
                            "-q:v", "2", str(tmp)], capture_output=True)
    if tmp.exists():
        import cv2
        bgr = cv2.imread(str(tmp))
        if bgr is not None:
            return bgr[:, :, ::-1]  # BGR→RGB for matplotlib
    return None


def fig_annotated_image(stats, scene):
    """First cropped frame with the fitted orbit + centre overlaid (cropped space)."""
    cal = stats["calibration"]
    cx, cy = cal.get("cx_px"), cal.get("cy_px")
    r_fit_px = cal.get("r_fit_px")
    frame = _first_frame()
    fig, ax = plt.subplots(figsize=(6, 6))
    if frame is not None:
        ax.imshow(frame)
    if None not in (cx, cy) and r_fit_px:
        ax.add_patch(plt.Circle((cx, cy), r_fit_px, fill=False, color="#00E676", lw=2.5))
        ax.plot([cx], [cy], "+", color="#00E676", ms=14, mew=2)
        ax.annotate(f"r = {_fmt(cal.get('r_fit_m'), 3, 'm')}",
                    (cx + r_fit_px, cy), color="#00E676", fontsize=11,
                    va="center", ha="left",
                    bbox=dict(fc="black", ec="none", alpha=0.6, pad=2))
    ax.set_title(_title(scene, "Scene geometry"))
    ax.set_xlabel("x (px, cropped)")
    ax.set_ylabel("y (px, cropped)")
    ax.grid(False)
    fig.tight_layout()
    fig.savefig(PLOTS / "annotated_image.png")
    plt.close(fig)


def fig_trajectory(stats, cols, scene):
    """2-D orbit in metres (cropped space) + the fitted reference circle.

    Returns the exact x_px,y_px arrays scattered, for figure_qa.json provenance.
    """
    cal = stats["calibration"]
    cx, cy = cal.get("cx_px"), cal.get("cy_px")
    ppm = cal.get("px_per_m") or 1.0
    r_fit_m = cal.get("r_fit_m")
    x_px, y_px = cols.get("x_px"), cols.get("y_px")
    m = np.isfinite(x_px) & np.isfinite(y_px)
    xp, yp = x_px[m], y_px[m]
    x_m = (xp - cx) / ppm
    y_m = (yp - cy) / ppm
    labels = stats.get("phases", {}).get("phase_labels") or []
    pl = np.array(labels)[m] if labels else None

    fig, ax = plt.subplots(figsize=(6, 6))
    if pl is not None:
        for lab in np.unique(pl):
            sel = pl == lab
            ax.scatter(x_m[sel], y_m[sel], s=10,
                       color=PHASE_COLOURS.get(str(lab).upper(), "#1E88E5"),
                       label=str(lab).title())
        ax.legend(fontsize=8, loc="best")
    else:
        ax.scatter(x_m, y_m, s=10, color="#1E88E5")
    if r_fit_m:
        ax.add_patch(plt.Circle((0, 0), r_fit_m, fill=False, ls="--",
                                 color="#37474F", lw=1.8))
    ax.plot([0], [0], "+", color="black", ms=12, mew=2)
    ax.set_aspect("equal", "box")
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.set_title(_title(scene, "Trajectory"))
    ax.invert_yaxis()  # image y grows downward
    fig.tight_layout()
    fig.savefig(PLOTS / "trajectory.png")
    plt.close(fig)
    return xp, yp


def fig_annotated_image_basic(stats, scene):
    """Basic-tier annotated frame: just the circular path + the radius, in plain
    language. No axis/pixel jargon, no vectors — one idea (it goes in a circle, this
    far out). Reuses first_frame.jpg written by fig_annotated_image."""
    cal = stats["calibration"]
    cx, cy = cal.get("cx_px"), cal.get("cy_px")
    r_fit_px = cal.get("r_fit_px")
    obj = stats.get("object_name") or scene or "object"
    frame = _first_frame()
    fig, ax = plt.subplots(figsize=(6, 6))
    if frame is not None:
        ax.imshow(frame)
    if None not in (cx, cy) and r_fit_px:
        ax.add_patch(plt.Circle((cx, cy), r_fit_px, fill=False, color="#00E676", lw=2.5))
        ax.plot([cx], [cy], "+", color="#00E676", ms=14, mew=2)
        # radius as a labelled arrow from the centre outward (plain words, no symbol)
        ax.annotate("", xy=(cx + r_fit_px, cy), xytext=(cx, cy),
                    arrowprops=dict(arrowstyle="->", color="#00E676", lw=2.2))
        ax.text(cx + r_fit_px / 2, cy, f"radius {_fmt(cal.get('r_fit_m'), 2, 'm')}",
                color="white", fontsize=12, va="bottom", ha="center",
                bbox=dict(fc="black", ec="none", alpha=0.6, pad=2))
    ax.set_title(_title(scene, f"The {obj} moves in a circle"))
    ax.axis("off")  # a novice doesn't need pixel coordinates
    fig.tight_layout()
    fig.savefig(PLOTS / "annotated_image_basic.png")
    plt.close(fig)


def fig_trajectory_basic(stats, cols, scene):
    """Basic-tier path: the traced points as one circle, single colour, no phase
    legend or per-frame colouring — shows 'it keeps coming back around', nothing more."""
    cal = stats["calibration"]
    cx, cy = cal.get("cx_px"), cal.get("cy_px")
    ppm = cal.get("px_per_m") or 1.0
    r_fit_m = cal.get("r_fit_m")
    x_px, y_px = cols.get("x_px"), cols.get("y_px")
    m = np.isfinite(x_px) & np.isfinite(y_px)
    x_m = (x_px[m] - cx) / ppm
    y_m = (y_px[m] - cy) / ppm
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(x_m, y_m, s=10, color="#1E88E5")
    if r_fit_m:
        ax.add_patch(plt.Circle((0, 0), r_fit_m, fill=False, ls="--",
                                 color="#37474F", lw=1.8))
    ax.plot([0], [0], "+", color="black", ms=12, mew=2)
    ax.set_aspect("equal", "box")
    ax.set_xlabel("distance across (m)")
    ax.set_ylabel("distance up/down (m)")
    ax.set_title(_title(scene, "The circular path it traced"))
    ax.invert_yaxis()
    fig.tight_layout()
    fig.savefig(PLOTS / "trajectory_basic.png")
    plt.close(fig)


def _smooth_1rev(t, y, stats):
    """Moving average over ~one revolution. Averaging over exactly one period
    cancels a 1x/rev (and 2x/rev) sinusoid — so it removes the viewing-angle
    projection ripple while preserving the real slow trend. NaN-aware."""
    y = np.asarray(y, float)
    fps = (stats.get("video_info") or {}).get("fps") or 30.0
    T = (stats.get("period_and_frequency") or {}).get("period_s") or 0.0
    w = int(round(T * fps)) or max(5, len(y) // 20)
    w = max(5, w | 1)  # odd, >=5
    valid = np.isfinite(y)
    yy = np.where(valid, y, 0.0)
    k = np.ones(w)
    num = np.convolve(yy, k, mode="same")
    den = np.convolve(valid.astype(float), k, mode="same")
    return np.where(den > 0, num / den, np.nan)


def _series_plot(name, cols, stats, scene, col, ylabel, what, colour,
                 hline=None, hline_lbl=None, star_peak=False, smooth_trend=False):
    t = cols.get("time_s")
    y = cols.get(col)
    labels = stats.get("phases", {}).get("phase_labels") or []
    fig, ax = plt.subplots(figsize=(8, 5))
    _shade_phases(ax, t, labels)
    if smooth_trend:
        # Oblique-capture clip: the per-instant curve is a projection artifact. Show the
        # raw values faintly and the 1-revolution trend boldly (the real physics).
        ax.plot(t, y, color=colour, lw=0.8, alpha=0.22)
        ax.plot(t, _smooth_1rev(t, y, stats), color=colour, lw=2.6,
                label="1-revolution trend")
        ax.legend(fontsize=8, loc="best")
    else:
        ax.plot(t, y, color=colour, lw=1.6)
    if hline is not None and np.isfinite(hline):
        ax.axhline(hline, ls="--", color="#455A64", lw=1.2,
                   label=hline_lbl or None)
        if hline_lbl:
            ax.legend(fontsize=8, loc="best")
    if star_peak and not smooth_trend:  # the raw peak is the ripple artifact — don't mark it
        yy = np.where(np.isfinite(y), y, -np.inf)
        if np.isfinite(yy).any():
            i = int(np.nanargmax(yy))
            ax.plot([t[i]], [y[i]], "*", color="#FFB300", ms=16,
                    markeredgecolor="black")
    ax.set_xlabel("time (s)")
    ax.set_ylabel(ylabel)
    ax.set_title(_title(scene, what))
    fig.tight_layout()
    fig.savefig(PLOTS / name)
    plt.close(fig)


def fig_annotated_table(stats, scene):
    s, pf = stats["summary"], stats["period_and_frequency"]
    cal, st = stats["calibration"], stats["stable_phase"]
    rows = [
        ("Mean radius", _fmt(s.get("mean_r_m"), 3), "m"),
        ("Std radius", _fmt(s.get("std_r_m"), 3), "m"),
        ("Stable angular velocity", _fmt(st.get("stable_mean_omega"), 2), "rad/s"),
        ("Mean centripetal accel.", _fmt(s.get("mean_ac"), 2), "m/s^2"),
        ("Max centripetal accel.", _fmt(s.get("max_ac"), 2), "m/s^2"),
        ("Stable centripetal accel.", _fmt(st.get("stable_mean_ac"), 2), "m/s^2"),
        ("Mean tangential speed", _fmt(s.get("mean_v"), 2), "m/s"),
        ("Period", _fmt(pf.get("period_s"), 2), "s"),
        ("Frequency", _fmt(pf.get("frequency_hz"), 2), "Hz"),
        ("Fitted radius", _fmt(cal.get("r_fit_m"), 3), "m"),
    ]
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.axis("off")
    tbl = ax.table(cellText=[[r[1], r[2]] for r in rows],
                   rowLabels=[r[0] for r in rows],
                   colLabels=["Value", "Unit"], loc="center", cellLoc="center")
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(10)
    tbl.scale(1, 1.5)
    ax.set_title(_title(scene, "Key measurements"))
    fig.tight_layout()
    fig.savefig(PLOTS / "annotated_table.png")
    plt.close(fig)


def fig_summary_panel(scene):
    """2×4 composite of the eight individual panels, via cv2 (deterministic)."""
    import cv2
    order = [
        "annotated_image.png", "trajectory.png",
        "annotated_graph.png", "omega_t.png",
        "radius_t.png", "theta_t.png",
        "ac_t.png", "annotated_table.png",
    ]
    cell_w = 800
    tiles = []
    for name in order:
        p = PLOTS / name
        img = cv2.imread(str(p)) if p.exists() else None
        if img is None:
            img = np.full((int(cell_w * 0.62), cell_w, 3), 240, np.uint8)
        h = int(img.shape[0] * cell_w / img.shape[1])
        tiles.append(cv2.resize(img, (cell_w, h)))
    row_h = max(t.shape[0] for t in tiles)
    tiles = [cv2.copyMakeBorder(t, 0, row_h - t.shape[0], 0, 0,
                                cv2.BORDER_CONSTANT, value=(255, 255, 255)) for t in tiles]
    rows = [np.hstack(tiles[i:i + 2]) for i in range(0, 8, 2)]
    panel = np.vstack(rows)
    cv2.imwrite(str(PLOTS / "summary_panel.png"), panel)


# ── entrypoint ───────────────────────────────────────────────────────────────

def main() -> int:
    PLOTS.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update(STYLE)
    stats = json.loads((DATA / "stats.json").read_text())
    cols = _load_csv()
    scene = stats.get("scene_title") or stats.get("object_name") or ""

    # Oblique-capture clips have a per-instant omega ripple that is a viewing-angle
    # projection artifact, not real motion. When flagged, the omega(t)/a_c(t) plots show
    # the 1-revolution trend (bold) over a faint raw trace, so the artifact ripple is not
    # presented as physics. Data/stats are unchanged — only the plotted curve is smoothed.
    unreliable = False
    try:
        from .. import quality_signals
        sig = quality_signals.compute(DATA / "kinematics.csv", stats)
        unreliable = "per_instant_omega_unreliable" in sig.get("flags", [])
    except Exception:
        unreliable = False

    s, st, pf = stats["summary"], stats["stable_phase"], stats["period_and_frequency"]
    stable_omega = st.get("stable_mean_omega")
    mean_r = s.get("mean_r_m")
    stable_ac = st.get("stable_mean_ac")

    fig_annotated_image(stats, scene)
    fig_annotated_image_basic(stats, scene)  # simplified frame for the basic tier
    traj_x, traj_y = fig_trajectory(stats, cols, scene)
    fig_trajectory_basic(stats, cols, scene)  # single-colour path for the basic tier
    # ω(t) with phase bands == the "annotated graph"
    _series_plot("annotated_graph.png", cols, stats, scene, "omega_rad_s",
                 "angular velocity (rad/s)", "Angular velocity & phases",
                 TRACE["omega"], hline=stable_omega, hline_lbl="stable mean",
                 smooth_trend=unreliable)
    _series_plot("omega_t.png", cols, stats, scene, "omega_rad_s",
                 "angular velocity (rad/s)", "Angular velocity", TRACE["omega"],
                 hline=stable_omega, hline_lbl="stable mean", smooth_trend=unreliable)
    _series_plot("ac_t.png", cols, stats, scene, "ac_m_s2",
                 "centripetal acceleration (m/s^2)", "Centripetal acceleration",
                 TRACE["ac"], hline=stable_ac, hline_lbl="stable mean", star_peak=True,
                 smooth_trend=unreliable)
    _series_plot("radius_t.png", cols, stats, scene, "r_m",
                 "radius (m)", "Orbit radius", TRACE["r"], hline=mean_r,
                 hline_lbl="mean", smooth_trend=unreliable)
    _series_plot("theta_t.png", cols, stats, scene, "theta_rad",
                 "angle (rad)", "Unwrapped angle", TRACE["theta"])
    _series_plot("v_t.png", cols, stats, scene, "v_m_s",
                 "tangential speed (m/s)", "Tangential speed", TRACE["v"],
                 hline=s.get("mean_v"), hline_lbl="mean", smooth_trend=unreliable)
    fig_annotated_table(stats, scene)
    fig_summary_panel(scene)

    # Provenance for the deterministic gate: report the EXACT cropped arrays we
    # scattered for trajectory.png. Recomputed from kinematics.csv by construction,
    # so verify_figures always passes — the full-frame mistake is unrepresentable.
    qa = {"trajectory": {
        "x_min": float(np.min(traj_x)), "x_max": float(np.max(traj_x)),
        "y_min": float(np.min(traj_y)), "y_max": float(np.max(traj_y)),
        "source": "kinematics.csv:x_px,y_px",
    }}
    (PLOTS / "figure_qa.json").write_text(json.dumps(qa, indent=2))
    print(f"FIGURES OK — wrote 9 plots + summary_panel.png + 2 basic-tier variants "
          f"to {PLOTS}/ (scene='{scene}')")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
