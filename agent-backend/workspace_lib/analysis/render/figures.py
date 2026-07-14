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
import textwrap
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from ..common import canonical_omega, dedup_display_name

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
PHASE_WORDS = {"INCREASE": "speeding up", "STABLE": "steady", "DECREASE": "slowing down"}
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


def _title(scene: str, what: str, width: int = 40) -> str:
    """Figure title, wrapped so a long "<what> — <scene>" never runs off the axes and
    gets clipped to "…a playground whe" (A8). textwrap inserts real newlines, which
    tight_layout then makes room for, rather than relying on matplotlib's flaky wrap=True."""
    full = f"{what} — {scene}" if scene else what
    return textwrap.fill(full, width=width) if len(full) > width else full


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


def _phases_trustworthy(stats, labels) -> bool:
    """False when the per-frame phase labels CONTRADICT the authoritative motion type: a
    non-uniform (accelerating/decelerating) clip whose labels collapsed to a single STABLE run.
    That can happen when a clip's speed change is too small/noisy to clear the labeller's
    magnitude floor (kinematics `_phases` labels |ω| off the P90 of |dω/dt| with a floor tied to
    the ω range), so it collapses to STABLE. Calling that "steady" would be a lie, so callers skip the
    phase shading/words and the manifest omits phases; the ω(t) curve itself shows the change.
    Uniform clips (is_clip_average False) label STABLE legitimately and stay trusted. Once the
    labeller emits a real INCREASE/DECREASE the contradiction clears and phases render again."""
    _v, is_clip_average = canonical_omega(stats)
    if not is_clip_average:
        return True
    return bool({str(lab).upper() for lab in (labels or [])} & {"INCREASE", "DECREASE"})


def _shade_phases(ax, t, labels):
    """Shade each motion phase AND print its plain-language word ("speeding up" / "steady" /
    "slowing down") at the band centre, so the reader sees WHERE the spin changes without
    decoding a colour key. Bands too narrow to fit the word keep the colour but stay unlabelled.
    Callers pass already-vetted labels (see `_phases_trustworthy`) — an empty list draws nothing."""
    if t is None or len(t) == 0 or not labels:
        return
    n = min(len(t), len(labels))
    total = float(t[n - 1] - t[0]) or 1.0
    trans = ax.get_xaxis_transform()  # x in data coords, y in axes fraction
    for s, e, lab in _phase_spans(labels):
        c = PHASE_COLOURS.get(str(lab).upper())
        if not (c and e > s and s < len(t)):
            continue
        t0, t1 = t[s], t[min(e, len(t)) - 1]
        ax.axvspan(t0, t1, color=c, alpha=0.12, lw=0)
        word = PHASE_WORDS.get(str(lab).upper())
        if word and (t1 - t0) >= 0.16 * total:  # wide enough to fit the label
            ax.text((t0 + t1) / 2, 0.96, word, transform=trans, ha="center", va="top",
                    fontsize=8, color=c, fontweight="bold",
                    bbox=dict(fc="white", ec=c, alpha=0.75, boxstyle="round,pad=0.2"))


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


_ANNOT_YELLOW = "#FFD600"       # value/vector colour (matches the P-MAGIC app annotation)
_ANNOT_GREEN = "#00E676"        # fitted-orbit colour


def _var_chip(ax, x, y, symbol, value, sym_color="#C62828"):
    """One variable annotation in the P-MAGIC style: the SYMBOL in a white rounded chip, then its
    VALUE+unit in a yellow rounded chip just to the right. (r, a → red symbol; ω → dark.)"""
    ax.text(x, y, symbol, color=sym_color, fontsize=13, fontweight="bold", va="center", ha="center",
            bbox=dict(boxstyle="round,pad=0.32", fc="white", ec="#222", lw=1.3), zorder=7)
    ax.annotate(value, (x, y), textcoords="offset points", xytext=(22, 0),
                color="black", fontsize=11, fontweight="bold", va="center", ha="left",
                bbox=dict(boxstyle="round,pad=0.32", fc=_ANNOT_YELLOW, ec="#222", lw=1.0), zorder=7)


def fig_annotated_image(stats, scene):
    """First cropped frame with the fitted orbit + the three centripetal-motion variables
    annotated in the P-MAGIC app style (green orbit; yellow radius line, tangential ω arrow, and
    inward centripetal-acceleration arrow; each with a symbol chip + a yellow value chip)."""
    cal = stats["calibration"]
    cx, cy = cal.get("cx_px"), cal.get("cy_px")
    r_fit_px = cal.get("r_fit_px")
    r_m = cal.get("r_fit_m")
    a_c = (stats.get("summary") or {}).get("mean_ac")
    frame = _first_frame()
    fig, ax = plt.subplots(figsize=(6, 6))
    if frame is not None:
        ax.imshow(frame)
    if None not in (cx, cy) and r_fit_px:
        ax.add_patch(plt.Circle((cx, cy), r_fit_px, fill=False, color=_ANNOT_GREEN, lw=3))
        ax.plot([cx], [cy], "+", color=_ANNOT_GREEN, ms=14, mew=2.5)
        # r — yellow radius line from the centre out to the left edge of the orbit.
        ax.annotate("", xy=(cx - r_fit_px, cy), xytext=(cx, cy),
                    arrowprops=dict(arrowstyle="-", color=_ANNOT_YELLOW, lw=3), zorder=5)
        if r_m is not None:
            _var_chip(ax, cx - 0.66 * r_fit_px, cy + 0.05 * r_fit_px, "r", _fmt(r_m, 3, "m"))
        # ω — curved tangential arrow along the bottom arc, direction from the sign of ω (matplotlib
        # renders the real Unicode glyph; the cv2 video overlay in annotate.py cannot — see its note).
        omega_val, _oca = canonical_omega(stats)
        if omega_val is not None:
            ccw = omega_val >= 0
            ax.annotate("", xy=(cx + (0.55 if ccw else -0.55) * r_fit_px, cy + r_fit_px),
                        xytext=(cx + (-0.55 if ccw else 0.55) * r_fit_px, cy + r_fit_px),
                        arrowprops=dict(arrowstyle="-|>", color=_ANNOT_YELLOW, lw=3,
                                        connectionstyle=f"arc3,rad={0.32 if ccw else -0.32}"), zorder=5)
            _var_chip(ax, cx - 0.35 * r_fit_px, cy + r_fit_px + 0.14 * r_fit_px, "ω",
                      _fmt(abs(omega_val), 2, "rad/s"), sym_color="#111")
        # a_c — inward (centripetal) arrow from a point on the upper-right of the orbit pointing
        # toward the centre (stopped short of the centre marker so it doesn't crowd the r line).
        if a_c is not None:
            sx, sy = cx + 0.64 * r_fit_px, cy - 0.64 * r_fit_px
            ax.annotate("", xy=(cx + 0.40 * r_fit_px, cy - 0.40 * r_fit_px), xytext=(sx, sy),
                        arrowprops=dict(arrowstyle="-|>", color=_ANNOT_YELLOW, lw=3), zorder=5)
            _var_chip(ax, sx - 0.02 * r_fit_px, sy - 0.10 * r_fit_px, "a", _fmt(a_c, 2, "m/s²"))
    ax.set_title(_title(scene, "Scene geometry"))
    ax.axis("off")
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


# CVD-safe categorical dots for the 90/180/270/360-degree milestones, validated with the
# dataviz palette validator (light surface: all checks pass, worst adjacent ΔE 53+). They
# echo the tier accent colours (blue/orange/purple/green) for visual coherence.
_MILESTONE_COLOURS = ["#1565C0", "#EF6C00", "#8E24AA", "#2E7D32"]


def fig_angle_points_basic(stats, cols, scene, unreliable=False):
    """Basic-tier "the angle grows with time" picture: the traced circular path (faint) with
    a coloured, directly-labelled dot at each 90/180/270/360-degree milestone ("1.0 s · 90°
    · a quarter turn"), a start marker and a sweep-direction arc. Reuses the basic-trajectory
    coordinate math and imports ``angle_milestones`` from ``..material_seed`` so the dots and
    the numbers the prose narrates come from ONE computation and cannot disagree.

    On an oblique clip the seed already drops the quarter-turn milestones (projection-
    distorted), so only the robust 180°/360° dots are drawn."""
    from ..material_seed import angle_milestones
    cal = stats["calibration"]
    cx, cy = cal.get("cx_px"), cal.get("cy_px")
    ppm = cal.get("px_per_m") or 1.0
    r_fit_m = cal.get("r_fit_m")
    x_px, y_px, t, active = (cols.get("x_px"), cols.get("y_px"),
                             cols.get("time_s"), cols.get("active"))
    m = np.isfinite(x_px) & np.isfinite(y_px) & np.isfinite(t)
    if active is not None:
        m = m & (active >= 0.5)
    xm, ym, tm = (x_px[m] - cx) / ppm, (y_px[m] - cy) / ppm, t[m]
    t0 = tm[0] if len(tm) else 0.0
    milestones = angle_milestones(DATA / "kinematics.csv", unreliable=unreliable)

    fig, ax = plt.subplots(figsize=(6, 6))
    ax.plot(xm, ym, color="#B0BEC5", lw=1.0, alpha=0.75, zorder=1)  # faint full path
    if r_fit_m:
        ax.add_patch(plt.Circle((0, 0), r_fit_m, fill=False, ls="--",
                                 color="#90A4AE", lw=1.2, zorder=0))
    ax.plot([0], [0], "+", color="#455A64", ms=12, mew=2, zorder=2)
    if len(xm):
        ax.scatter([xm[0]], [ym[0]], s=70, facecolor="white",
                   edgecolor="#455A64", lw=1.8, zorder=4)
        ax.annotate("start", (xm[0], ym[0]), textcoords="offset points",
                    xytext=(6, -12), fontsize=9, color="#455A64")
    for i, ms in enumerate(milestones):
        if not len(tm):
            break
        j = int(np.argmin(np.abs((tm - t0) - ms["t_s"])))
        c = _MILESTONE_COLOURS[i % len(_MILESTONE_COLOURS)]
        ax.scatter([xm[j]], [ym[j]], s=120, color=c, edgecolor="white", lw=1.8, zorder=5)
        # Steer each label toward the centre so boxes stay inside the frame.
        dx, dy = (-11 if xm[j] > 0 else 11), (-11 if ym[j] > 0 else 11)
        ax.annotate(f"{ms['t_s']:.1f} s · {ms['angle_deg']}° · {ms['turn']}",
                    (xm[j], ym[j]), textcoords="offset points", xytext=(dx, dy),
                    ha="right" if dx < 0 else "left",
                    va="top" if dy < 0 else "bottom",
                    fontsize=9, color=c, fontweight="bold", zorder=6,
                    bbox=dict(fc="white", ec=c, alpha=0.9,
                              boxstyle="round,pad=0.25"))
        if i == 0:  # arc arrow from start toward the first milestone = sweep direction
            ax.annotate("", xy=(xm[j], ym[j]), xytext=(xm[0], ym[0]),
                        zorder=3, arrowprops=dict(
                            arrowstyle="-|>", color="#607D8B", lw=1.6,
                            connectionstyle="arc3,rad=0.3", shrinkA=8, shrinkB=10))
    # Degrees-per-second: turn the angular velocity into the plain "how fast the angle grows"
    # number the basic tier reasons with. Derived from canonical_omega (the ONE angular velocity
    # every surface quotes) so it can never disagree with the milestones above or the prose.
    # Only drawn for uniform motion — for a (de)accelerating clip the angle does NOT grow at a
    # constant rate, so a single "°/second" would contradict the evenly-spaced milestone dots.
    omega_val, oca = canonical_omega(stats)
    if omega_val is not None and not oca:
        dps = omega_val * 180.0 / np.pi
        ax.text(0.5, 0.015, f"the angle grows about {dps:.0f}° every second",
                transform=ax.transAxes, ha="center", va="bottom", fontsize=9.5,
                color="#37474F", fontweight="bold",
                bbox=dict(fc="white", ec="#90A4AE", alpha=0.92, boxstyle="round,pad=0.3"))
    lim = 1.45 * (r_fit_m or (np.nanmax(np.abs(np.concatenate([xm, ym]))) if len(xm) else 1))
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.set_aspect("equal", "box")
    ax.set_xlabel("distance across (m)")
    ax.set_ylabel("distance up/down (m)")
    ax.set_title(_title(scene, "The angle grows with time"))
    ax.invert_yaxis()
    fig.tight_layout()
    fig.savefig(PLOTS / "angle_points_basic.png")
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
    if not _phases_trustworthy(stats, labels):  # non-uniform clip mislabelled all-STABLE
        labels = []
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
    omega_val, omega_is_clip_avg = canonical_omega(stats)
    rows = [
        ("Mean radius", _fmt(s.get("mean_r_m"), 3), "m"),
        ("Std radius", _fmt(s.get("std_r_m"), 3), "m"),
        ("Angular velocity (clip avg)" if omega_is_clip_avg else "Stable angular velocity",
         _fmt(omega_val, 2), "rad/s"),
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


# ── annotation manifest (extends figure_qa.json) ─────────────────────────────

def _phase_sequence(stats):
    """Ordered, de-duplicated motion phases present (speeding up / steady / slowing down).
    Returns [] when the labels contradict the authoritative motion type (see
    `_phases_trustworthy`), so the manifest never asserts a false "steady" for a flick."""
    labels = (stats.get("phases", {}) or {}).get("phase_labels") or []
    if not _phases_trustworthy(stats, labels):
        return []
    friendly = {"INCREASE": "speeding up", "STABLE": "steady", "DECREASE": "slowing down"}
    seq = []
    for lab in labels:
        L = str(lab).upper()
        if L in ("INACTIVE", "IDLE"):
            continue
        if not seq or seq[-1]["label"] != L.lower():
            seq.append({"label": L.lower(), "meaning": friendly.get(L, L.lower())})
    return seq


def _annotation_manifest(stats):
    """Per-figure annotation manifest, written under figure_qa.json["annotations"]. Keyed by
    figure filename; material_tiers resolves tier -> figures (report.TIER_ARTIFACTS) -> these
    annotations so the prose describes the REAL overlays, and the Axis-4 annotation_correctness
    eval grounds prose claims against them. Defensive: any missing field is simply omitted."""
    cal = stats.get("calibration", {}) or {}
    omega_val, _oca = canonical_omega(stats)
    r_m = cal.get("r_fit_m")
    man = {}

    img = []
    if r_m is not None:
        img.append({"label": "radius", "symbol": "r", "value": _fmt(r_m, 3, "m"),
                    "target": "arrow from the centre to the object"})
    if omega_val is not None:
        img.append({"label": "angular velocity", "symbol": "ω",
                    "value": _fmt(abs(omega_val), 2, "rad/s"),
                    "target": "curved tangential arrow on the orbit showing the spin direction"})
    a_c = (stats.get("summary") or {}).get("mean_ac")
    if a_c is not None:
        img.append({"label": "centripetal acceleration", "symbol": "a",
                    "value": _fmt(a_c, 2, "m/s²"),
                    "target": "arrow pointing inward toward the centre"})
    if img:
        man["annotated_image.png"] = {
            "shows": "photo of the object with the fitted circle, and the radius, angular velocity "
                     "and centripetal acceleration marked",
            "annotations": img}
    if r_m is not None:
        man["annotated_image_basic.png"] = {
            "shows": "the same photo with just the circular path and how far out the object sits",
            "annotations": [{"label": "how far out it sits", "value": _fmt(r_m, 3, "m"),
                             "target": "arrow from the centre outward"}]}

    # Angle milestones live in the seed (not stats); include them if the seed is present.
    try:
        seed = json.loads((DATA / "material_seed.json").read_text())
        ms = seed.get("angle_milestones") or []
        if ms:
            man["angle_points_basic.png"] = {
                "shows": "the path with a coloured dot at each 90-degree milestone, labelled by time and turn",
                "annotations": [{"label": f"{m.get('t_s')} s", "value": f"{m.get('angle_deg')}°",
                                 "note": m.get("turn")} for m in ms]}
    except Exception:  # noqa: BLE001 — the manifest is best-effort provenance, never fatal
        pass

    phases = _phase_sequence(stats)
    for fig in ("omega_t.png", "annotated_graph.png"):
        man[fig] = {"shows": "angular velocity over time"}
        if phases:
            man[fig]["phases"] = phases
    man["ac_t.png"] = {"shows": "centripetal acceleration over time"}
    if phases:
        man["ac_t.png"]["phases"] = phases

    man["annotated_table.png"] = {
        "shows": "a table of the core measured values",
        "annotations": [{"label": lbl} for lbl in
                        ("radius", "angular velocity", "centripetal acceleration", "period", "frequency")]}
    return man


# ── entrypoint ───────────────────────────────────────────────────────────────

def main() -> int:
    PLOTS.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update(STYLE)
    stats = json.loads((DATA / "stats.json").read_text())
    cols = _load_csv()
    # Collapse the degenerate "<X> on <X>" composite so figure titles read "fan blade",
    # not "fan blade on fan blade" (shares the report/seed helper).
    scene = dedup_display_name(stats.get("scene_title") or stats.get("object_name"))

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
    # The ω(t) reference line matches the table/prose: clip-average on a (de)accelerating
    # clip (labelled so), the stable-phase mean only on a genuinely uniform spin.
    stable_omega, _omega_is_clip_avg = canonical_omega(stats)
    omega_hline_lbl = "clip average" if _omega_is_clip_avg else "stable mean"
    mean_r = s.get("mean_r_m")
    stable_ac = st.get("stable_mean_ac")

    fig_annotated_image(stats, scene)
    fig_annotated_image_basic(stats, scene)  # simplified frame for the basic tier
    traj_x, traj_y = fig_trajectory(stats, cols, scene)
    fig_trajectory_basic(stats, cols, scene)  # single-colour path for the basic tier
    fig_angle_points_basic(stats, cols, scene, unreliable=unreliable)  # angle-at-time dots
    # ω(t) with phase bands == the "annotated graph"
    _series_plot("annotated_graph.png", cols, stats, scene, "omega_rad_s",
                 "angular velocity (rad/s)", "Angular velocity & phases",
                 TRACE["omega"], hline=stable_omega, hline_lbl=omega_hline_lbl,
                 smooth_trend=unreliable)
    _series_plot("omega_t.png", cols, stats, scene, "omega_rad_s",
                 "angular velocity (rad/s)", "Angular velocity", TRACE["omega"],
                 hline=stable_omega, hline_lbl=omega_hline_lbl, smooth_trend=unreliable)
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
    qa["annotations"] = _annotation_manifest(stats)  # per-figure manifest for material + Axis-4 eval
    (PLOTS / "figure_qa.json").write_text(json.dumps(qa, indent=2))
    print(f"FIGURES OK — wrote 9 plots + summary_panel.png + 3 basic-tier variants "
          f"to {PLOTS}/ (scene='{scene}')")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
