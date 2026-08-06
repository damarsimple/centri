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
import math
import subprocess
import textwrap
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np

from ..common import canonical_omega, dedup_display_name, fit_orbit_ellipse, travel_sign
from . import palette as _PAL

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
# Band text on the shaded graphs. These describe the PLOTTED QUANTITY (a_c is increasing, ω is
# increasing), not the object — which is why they are not "speeding up"/"slowing down": that
# wording reads as a claim about the motion and is wrong on an a_c axis. The motion wording still
# exists, in `_phase_sequence` below, for the prose.
PHASE_WORDS = {"INCREASE": "increasing", "STABLE": "steady", "DECREASE": "decreasing"}
# A rest band shaded grey and said nothing, so the marker jitter inside it read as physics: on
# turntable-3 the tail reaches a_c 21.3 m/s² — 68% of that clip's largest ACTIVE value and 2.9x
# its mean — and every negative omega in the corpus outside the two counter-clockwise fans lives
# here. Name it. Kept OUT of PHASE_WORDS on purpose: that map also gates `_phase_significant`,
# which drops slivers, and a rest band must stay shaded however short it is.
REST_WORDS = {"INACTIVE": "not turning", "IDLE": "not turning"}
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


def _phase_significant(width_s: float) -> bool:
    """A MOTION phase is real (not a 1-2 frame despeckle sliver) when it lasts at least this
    long. ~0.12 s ≈ 3-4 frames at 30 fps — enough to be a genuine spin-up/coast segment. Keeps
    the manifest/prose ("three distinct phases") and the ω(t) figure in agreement: on the flick
    the STABLE transition between spin-up and coast-down is a single frame and must not count."""
    return width_s >= 0.12


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


def _rest_label_is_contradicted(y, s, e, ymax):
    """True when a band the segmenter called REST plainly contains motion.

    Printing "not turning" over a curve that visibly moves is worse than printing nothing: the
    reader trusts the word over the line. This happened for real — a band labelled "not turning"
    on `computerfan-4029` spanned samples reaching 24 rad/s, because the segmenter mis-marks
    bursts as INACTIVE and the label made that silent error into a printed falsehood. The word is
    suppressed whenever the data under it disagrees; fixing the SEGMENTATION is the separate,
    deeper job. Threshold is relative to the series, so it holds for rad/s and m/s^2 alike.
    """
    if y is None or ymax is None or not np.isfinite(ymax) or ymax <= 0:
        return False
    seg = np.asarray(y, dtype=float)[s:e]
    seg = seg[np.isfinite(seg)]
    if seg.size == 0:
        return False
    return float(np.nanmax(np.abs(seg))) > max(0.05 * float(ymax), 1e-9)


def _shade_phases(ax, t, labels, y=None):
    """Shade each motion phase AND print its plain-language word ("speeding up" / "steady" /
    "slowing down") at the band centre, so the reader sees WHERE the spin changes without
    decoding a colour key. A motion phase that survives only as a 1-2 frame despeckle sliver is
    skipped (see `_phase_significant`) so the figure agrees with the prose; every phase that IS
    drawn gets its word, with the label height staggered when adjacent bands sit close together
    (A5/C2 — the flick's short spin-up band used to draw unlabelled). INACTIVE rest bands keep
    their grey shading and now carry "not turning", so the jitter inside them cannot be read as
    motion. Callers pass already-vetted labels (see `_phases_trustworthy`) — an empty list draws
    nothing."""
    if t is None or len(t) == 0 or not labels:
        return
    n = min(len(t), len(labels))
    total = float(t[n - 1] - t[0]) or 1.0
    trans = ax.get_xaxis_transform()  # x in data coords, y in axes fraction
    rows_y = (0.96, 0.83, 0.70)
    row, last_cx = 0, None
    ymax = None
    if y is not None:
        finite = np.asarray(y, dtype=float)
        finite = finite[np.isfinite(finite)]
        ymax = float(np.nanmax(np.abs(finite))) if finite.size else None
    for s, e, lab in _phase_spans(labels):
        L = str(lab).upper()
        c = PHASE_COLOURS.get(L)
        if not (c and e > s and s < len(t)):
            continue
        t0, t1 = t[s], t[min(e, len(t)) - 1]
        width = t1 - t0
        if L in PHASE_WORDS and not _phase_significant(width):
            continue                                   # drop a sliver of a real motion phase
        ax.axvspan(t0, t1, color=c, alpha=0.12, lw=0)
        word = PHASE_WORDS.get(L) or REST_WORDS.get(L)
        # The shading stays (it is a colour, not a claim); the WORD goes, because it is a claim.
        if word and L in REST_WORDS and _rest_label_is_contradicted(y, s, e, ymax):
            word = None
        if word and width >= 0.06 * total:             # wide enough that a (short) label reads
            cx = (t0 + t1) / 2
            row = (row + 1) % len(rows_y) if last_cx is not None and (cx - last_cx) < 0.2 * total else 0
            # Word in BLACK on a white chip, with the band's colour kept as the chip border: the
            # coloured text was the weakest-contrast element on the figure.
            ax.text(cx, rows_y[row], word, transform=trans, ha="center", va="top",
                    fontsize=8, color="black", fontweight="bold",
                    bbox=dict(fc="white", ec=c, alpha=0.9, boxstyle="round,pad=0.25"))
            last_cx = cx


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


# Plain-language name for each symbol, as the app words them ("kecepatan linier" = linear speed —
# NOT "tangential velocity", which is our jargon, not the students').
_QUANTITY_NAMES = {"r": "RADIUS", "v": "LINEAR SPEED",
                   "ω": "ANGULAR SPEED", "a_c": "CENTRIPETAL ACCELERATION"}
# Basic tier: the SAME four arrows, named in plain words instead of symbols. The picture a
# beginner sees should carry MORE of the explanation than the one an advanced reader sees, not
# less — the beginner has the least text to fall back on. Keeping the no-symbols rule is what
# still separates this tier, so nothing here is a letter (and the on-frame glyphs are replaced
# by a plain dot, see `plain=` in fig_annotated_image).
_QUANTITY_NAMES_PLAIN = {
    "r": "how far out it sits\nfrom the centre",
    "v": "how fast it travels\nalong the circle",
    "ω": "how fast it sweeps\nround the centre",
    "a_c": "the inward pull that\nkeeps it on the circle",
}


def _halo(lw=3.0, color=None):
    """Outline behind a coloured mark so it stays legible over any photo. The outline takes the
    opposite lightness pole from the mark: a light mark on a white halo is no more readable than
    no halo at all, and the palette adapts marks to be light over dark footage."""
    import matplotlib.patheffects as pe
    fg = "white" if color is None else _PAL.to_hex(_PAL.casing(_hex_bgr(color)))
    return [pe.withStroke(linewidth=lw, foreground=fg)]


def _hex_bgr(h):
    h = h.lstrip("#")
    return (int(h[4:6], 16), int(h[2:4], 16), int(h[0:2], 16))


def _symbol(ax, xy, text, color, fontsize=17, plain=False):
    """The bare SYMBOL, drawn beside its arrow (never on it) in the arrow's own colour.

    ``plain=True`` (basic tier, whose rule is no symbols anywhere) draws a small filled dot in
    the same place instead: the leader line still has something to land on, so each arrow is
    still unambiguously joined to its own worded callout, without a letter on the picture."""
    if plain:
        ax.plot([xy[0]], [xy[1]], "o", color=color, ms=8, mec="white", mew=1.6, zorder=8)
        return
    ax.text(xy[0], xy[1], text, color=color, fontsize=fontsize, fontweight="bold",
            va="center", ha="center", zorder=8, path_effects=_halo(3.5, color))


def _place_callouts(ax, items, W, H):
    """Park each quantity's name+value in the margin BESIDE the photo, joined to its symbol by a
    thin leader line — the P-MAGIC diagram's convention. Keeping the descriptive text off the frame
    is what fixes the old chips-on-top-of-the-arrow overlap: nothing but a thin arrow and a
    one-glyph symbol is ever drawn over the footage.

    Each callout goes in the margin NEARER its own symbol and the boxes on a side are stacked in
    the symbols' own top-to-bottom order, so a leader line never crosses the frame or another
    callout. `items` = [(anchor_xy, name, value, colour), ...]."""
    sides = {"left": [], "right": []}
    for it in items:
        sides["left" if it[0][0] < 0.5 * W else "right"].append(it)
    for side, group in sides.items():
        group.sort(key=lambda it: it[0][1])
        slots = {1: [0.5], 2: [0.26, 0.74], 3: [0.16, 0.5, 0.84],
                 4: [0.12, 0.38, 0.64, 0.9]}.get(len(group), [])
        x = (-0.04 * W) if side == "left" else (1.04 * W)
        for (xy, name, value, color), y_frac in zip(group, slots):
            ax.annotate(f"{name}\n{value}" if value else name, xy=xy, xycoords="data",
                        xytext=(x, y_frac * H), textcoords="data",
                        ha="right" if side == "left" else "left", va="center",
                        fontsize=9.5, color="#212121", linespacing=1.5, zorder=9,
                        bbox=dict(boxstyle="round,pad=0.4", fc="white", ec=color, lw=1.6),
                        arrowprops=dict(arrowstyle="-", color="#78909C", lw=1.1,
                                        shrinkA=3, shrinkB=9,
                                        connectionstyle="arc3,rad=%.2f" %
                                        (0.14 if side == "left" else -0.14)))


def fig_annotated_image(stats, scene, cols=None, plain=False,
                        out_name="annotated_image.png"):
    """First cropped frame with the fitted orbit and the four circular-motion quantities marked in
    the convention of the P-MAGIC teaching diagram (`image_rotating.png`): every quantity gets its
    own coloured arrow, the SYMBOL sits beside the arrow, and the descriptive name + value live in a
    boxed callout in the margin, joined by a leader line.

    Linear speed v (straight tangent) and angular speed ω (small curved arc) are DIFFERENT arrows —
    the earlier single "curved tangential ω arrow" conflated the two, which is exactly what the
    reference diagram separates. All four arrows spring from one point: the object's real position
    in the first frame, so the picture reads as "this object, here, right now".

    ``plain=True`` draws the SAME four arrows for the basic tier, but names them in words instead
    of symbols and quotes only the two values that tier is allowed to meet (the radius in metres
    and the turn rate as turns per second — never rad/s, never an acceleration). It used to get a
    stripped frame showing only the radius, which put the least explanation in front of the reader
    with the least text to fall back on."""
    cal = stats["calibration"]
    cx, cy = cal.get("cx_px"), cal.get("cy_px")
    r_fit_px = cal.get("r_fit_px")
    r_m = cal.get("r_fit_m")
    summ = stats.get("summary") or {}
    a_c, v_m_s = summ.get("mean_ac"), summ.get("mean_v")
    names = _QUANTITY_NAMES_PLAIN if plain else _QUANTITY_NAMES
    # Turns per second is the ONLY rate the basic tier may see as a number (rad/s is banned
    # there), so the turn-rate callout switches unit with the tier rather than dropping out.
    turns_per_s = (stats.get("period_and_frequency") or {}).get("frequency_hz")
    frame = _first_frame()
    H, W = (frame.shape[0], frame.shape[1]) if frame is not None else (1000, 1000)
    # Colours adapted to this clip's footage, from the same module and the same frames the video
    # overlay uses — so the still and the video show one palette, not two (see render.palette).
    # Callout boxes sit on the white margin, not on the photo, so their borders keep the CANONICAL
    # hue — the adapted colour is tuned for legibility against the footage and can be too light to
    # read on white. Same hue either way, so the callout still reads as belonging to its symbol.
    base = {k: _PAL.to_hex(v) for k, v in _PAL.BASE.items()}
    pal = {k: _PAL.to_hex(v) for k, v in _PAL.clip_palette(
        _cropped_video(), (cols or {}).get("theta_rad", []), cx, cy, r_fit_px).items()} \
        if (None not in (cx, cy) and r_fit_px) else {k: _PAL.to_hex(v) for k, v in
                                                    dict(_PAL.BASE, centre=_PAL.CENTRE).items()}
    # Margins left and right of the photo, where the callouts live (reference layout).
    g = 0.44 * W
    fig, ax = plt.subplots(figsize=(min(13.0, 6.0 * (W + 2 * g) / H), 6.0))
    if frame is not None:
        ax.imshow(frame)
    if None not in (cx, cy) and r_fit_px:
        # ω and a_c are clip AVERAGES on a (de)accelerating clip, pinned here to one frozen frame;
        # tag them "(avg)" so the still image cannot silently contradict the honesty box (on a clip
        # where ω ran 0->9.8, an unqualified "ω 5.79" reads as an instantaneous value). r is a
        # static geometry value, never averaged, so it carries no tag. (C3)
        omega_val, _oca = canonical_omega(stats)
        avg = " (avg)" if _oca else ""

        # The object's own position in this frame — the anchor every vector springs from. Falls
        # back to the upper-right of the orbit when the track has no finite first sample.
        # Use the measured centroid itself, not its bearing re-projected onto the fitted
        # circle: on an orbit that images as an ellipse those are different points, and
        # the marker then sits off the object (mean 186 px on roundabout-4046).
        th0 = -math.pi / 4
        px_, py_ = cx + r_fit_px * math.cos(th0), cy + r_fit_px * math.sin(th0)
        if cols is not None:
            xs, ys = cols.get("x_px"), cols.get("y_px")
            if xs is not None and ys is not None:
                ok = np.isfinite(xs) & np.isfinite(ys)
                if ok.any():
                    j = int(np.argmax(ok))
                    th0 = math.atan2(ys[j] - cy, xs[j] - cx)
                    px_, py_ = float(xs[j]), float(ys[j])
        ux, uy = math.cos(th0), math.sin(th0)          # outward radial unit vector
        s = travel_sign(stats)                          # never sign(omega_val) — see common
        tx, ty = -uy * s, ux * s                        # unit vector along the motion

        # Trace the shape the orbit ACTUALLY has in the image — a circle seen off-axis
        # is an ellipse, and a drawn circle then floats off the object it claims to
        # follow. Picture only; r, v, ω, a_c all still come from the circle fit.
        orbit_fit = fit_orbit_ellipse((cols or {}).get("x_px", []),
                                      (cols or {}).get("y_px", []))
        if orbit_fit is not None:
            ex, ey, semi_major, semi_minor, ang = orbit_fit
            ax.add_patch(mpatches.Ellipse((ex, ey), 2 * semi_major, 2 * semi_minor,
                                          angle=ang, fill=False, color=pal["orbit"],
                                          lw=2.6, path_effects=_halo(4.5, pal["orbit"])))
        else:
            ax.add_patch(plt.Circle((cx, cy), r_fit_px, fill=False, color=pal["orbit"], lw=2.6,
                                    path_effects=_halo(4.5, pal["orbit"])))
        ax.plot([cx], [cy], "+", color=pal["orbit"], ms=15, mew=2.5,
                path_effects=_halo(4.5, pal["orbit"]))
        ax.plot([px_], [py_], "o", color="#1565C0", ms=8, mec="white", mew=1.6, zorder=6)

        calls = []   # (symbol anchor, name, value, colour) → margin callouts, placed at the end

        # r — double-headed arrow along the object's OWN radius, centre to object, because that is
        # where the radius is. It used to be drawn PERPENDICULAR to that radius so it could not lie
        # under the a_c arrow (which runs along the same line); the cost was an arrow labelled "r",
        # springing from the centre of rotation, pointing at empty space.
        # The overlap is solved the way a drawing does it: offset the dimension line sideways, with
        # the arrow spanning exactly centre -> object. a_c keeps the true radial line.
        # r and a_c are collinear by physics — both run along the radius. They are split
        # SYMMETRICALLY about that line, r one side and a_c the other, so each keeps its true
        # direction and neither hides the other.
        rpx, rpy = -uy, ux                              # perpendicular to the radius
        if (rpx * ty - rpy * tx) < 0:                   # r sits on the side AWAY from travel
            rpx, rpy = -rpx, -rpy
        r_off = 0.13 * r_fit_px
        ax.annotate("", xy=(cx + ux * r_fit_px + rpx * r_off, cy + uy * r_fit_px + rpy * r_off),
                    xytext=(cx + rpx * r_off, cy + rpy * r_off),
                    arrowprops=dict(arrowstyle="<|-|>", color=pal["r"], lw=2.6,
                                    shrinkA=0, shrinkB=0, path_effects=_halo(4.5, pal["r"])), zorder=5)
        r_sym = (cx + ux * 0.52 * r_fit_px + rpx * (r_off + 0.13 * r_fit_px),
                 cy + uy * 0.52 * r_fit_px + rpy * (r_off + 0.13 * r_fit_px))
        _symbol(ax, r_sym, "r", pal["r"], plain=plain)
        if r_m is not None:
            calls.append((r_sym, names["r"], _fmt(r_m, 3, "m"), base["r"]))

        # v — straight tangent arrow at the object, pointing the way it travels.
        vlen = 0.78 * r_fit_px
        ax.annotate("", xy=(px_ + tx * vlen, py_ + ty * vlen), xytext=(px_, py_),
                    arrowprops=dict(arrowstyle="-|>,head_width=0.32,head_length=0.6", color=pal["v"],
                                    lw=2.8, shrinkA=0, shrinkB=0, path_effects=_halo(4.5, pal["v"])), zorder=5)
        v_sym = (px_ + tx * 0.70 * vlen + ux * 0.24 * r_fit_px,
                 py_ + ty * 0.70 * vlen + uy * 0.24 * r_fit_px)
        _symbol(ax, v_sym, "v", pal["v"], plain=plain)
        if plain:
            calls.append((v_sym, names["v"], "", base["v"]))
        elif v_m_s is not None:
            calls.append((v_sym, names["v"], _fmt(v_m_s, 2, "m/s") + avg, base["v"]))

        # a_c — straight arrow from the object toward the centre (stopped short of the centre mark),
        # offset to the OPPOSITE side of the radius from r.
        acx, acy = -rpx * r_off, -rpy * r_off
        ax.annotate("", xy=(px_ - ux * 0.62 * r_fit_px + acx, py_ - uy * 0.62 * r_fit_px + acy),
                    xytext=(px_ + acx, py_ + acy),
                    arrowprops=dict(arrowstyle="-|>,head_width=0.32,head_length=0.6", color=pal["ac"],
                                    lw=2.8, shrinkA=0, shrinkB=0, path_effects=_halo(4.5, pal["ac"])), zorder=5)
        ac_sym = (px_ - ux * 0.36 * r_fit_px + acx - rpx * 0.13 * r_fit_px,
                  py_ - uy * 0.36 * r_fit_px + acy - rpy * 0.13 * r_fit_px)
        _symbol(ax, ac_sym, "$a_c$", pal["ac"], plain=plain)
        if plain:
            calls.append((ac_sym, names["a_c"], "", base["ac"]))
        elif a_c is not None:
            calls.append((ac_sym, names["a_c"], _fmt(a_c, 2, "m/s²") + avg, base["ac"]))

        # ω — a SMALL curved arc curling the way it spins. This is the angular quantity: it is about
        # the turning, not about a direction of travel, which is why it is a separate mark from v
        # (reference diagram). Preferred spot is just OUTSIDE the orbit at the object; when the
        # object sits near the frame edge that lands off the photo entirely, floating on the margin
        # and colliding with the callouts, so it falls back to a small arc about the centre — on the
        # opposite side from the r arrow, hence clear of both r and the (radial) a_c arrow. Same
        # rule as the video overlay, so the two artifacts agree on where ω lives.
        d, rr = 0.30, 1.16 * r_fit_px
        w_sym = (cx + 1.40 * r_fit_px * math.cos(th0), cy + 1.40 * r_fit_px * math.sin(th0))
        pad = 0.06 * max(W, H)
        if not (pad <= w_sym[0] <= W - pad and pad <= w_sym[1] <= H - pad):
            th0_w = math.atan2(-rpy, -rpx)
            d, rr = 0.9, 0.32 * r_fit_px
            w_sym = (cx - rpx * 0.52 * r_fit_px, cy - rpy * 0.52 * r_fit_px)
        else:
            th0_w = th0
        a0, a1 = th0_w - s * d, th0_w + s * d
        ax.annotate("", xy=(cx + rr * math.cos(a1), cy + rr * math.sin(a1)),
                    xytext=(cx + rr * math.cos(a0), cy + rr * math.sin(a0)),
                    arrowprops=dict(arrowstyle="-|>,head_width=0.3,head_length=0.55", color=pal["w"],
                                    lw=2.8, shrinkA=0, shrinkB=0,
                                    connectionstyle=f"arc3,rad={-0.35 * s}",
                                    path_effects=_halo(4.5, pal["w"])), zorder=5)
        _symbol(ax, w_sym, "ω", pal["w"], plain=plain)
        if plain:
            val = (f"about {_fmt(turns_per_s, 2)} turns each second"
                   if isinstance(turns_per_s, (int, float)) else "")
            calls.append((w_sym, names["ω"], val, base["w"]))
        elif omega_val is not None:
            calls.append((w_sym, names["ω"],
                          _fmt(abs(omega_val), 2, "rad/s") + avg, base["w"]))

        _place_callouts(ax, calls, W, H)
    ax.set_xlim(-g, W + g)
    ax.set_ylim(H, 0)
    ax.set_aspect("equal")
    # The plain title must not restate the object — `_title` already appends the scene, and
    # "What the red phone is doing — red phone on black circular base" says it twice.
    ax.set_title(_title(scene, "What each arrow means" if plain else "Scene geometry",
                        width=52))
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(PLOTS / out_name)
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


def fig_annotated_image_basic(stats, scene, cols=None):
    """Basic-tier annotated frame — the SAME marked-up still the other two tiers get, with every
    label in plain words instead of symbols.

    It used to draw only the circular path and the radius: one idea, and the least explanation of
    the three tiers in front of the reader with the least text to fall back on. The figure is
    where a basic reader does most of the work, so it is the last thing that should be stripped
    down. What still separates the tier is the no-symbols rule, which `plain=True` keeps."""
    fig_annotated_image(stats, scene, cols, plain=True,
                        out_name="annotated_image_basic.png")


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


def _nice_step(raw):
    """Round a raw axis step up to a friendly value, so time markers land on 0.25/0.5/1 s
    boundaries rather than 0.32 s."""
    for s in (0.1, 0.2, 0.25, 0.5, 1.0, 2.0, 2.5, 5.0):
        if raw <= s:
            return s
    return 10.0


def fig_angle_points_basic(stats, cols, scene, unreliable=False):
    """Basic-tier "how the turning changes over time" picture: TURNS COMPLETED vs time.

    The cumulative swept angle (in whole turns) climbs from zero, and the SHAPE of that line
    is the story a single frozen frame cannot tell — a straight line is a steady spin, a line
    that bends flatter is slowing down, a line that steepens is speeding up (C5). This replaces
    the earlier spatial quarter-turn milestone dots, which could only ever show the FAST first
    turn (on the red-phone flick all four quarter-turns land in the first ~0.8 s, reading as
    steady) and so could not meet the basic objective "see that it is gradually slowing down".
    Uses the cumulative unwrapped angle from kinematics.csv, so the numbers cannot disagree
    with the rest of the material; ``unreliable`` (oblique capture) needs no special handling
    here because the cumulative angle is robust to the per-instant projection ripple."""
    t = np.asarray(cols.get("time_s"), float)
    th = np.asarray(cols.get("theta_rad"), float)
    active = cols.get("active")
    m = np.isfinite(t) & np.isfinite(th)
    if active is not None:
        m = m & (np.asarray(active, float) >= 0.5)
    t, th = t[m], th[m]
    if len(t) < 5:                    # too little motion to draw a curve — report skips a missing file
        return
    ts = t - t[0]
    # "Turns completed" is inherently cumulative and monotone (you cannot un-complete a turn);
    # running-max over the |swept angle| erases tiny back-and-forth jitter without inventing motion.
    turns = np.maximum.accumulate(np.abs(th - th[0])) / (2 * np.pi)

    mt = (stats.get("angular_acceleration") or {}).get("motion_type", "uniform")
    fig, ax = plt.subplots(figsize=(6.4, 4.6))
    ax.plot(ts, turns, color="#1565C0", lw=2.6, zorder=2)
    # A handful of evenly-time-spaced markers (~6 across the window) so the reader can compare
    # how many turns accrue in equal slices of time — the rise per slice shrinks as it slows.
    span = float(ts[-1]) if ts[-1] > 0 else 1.0
    step = _nice_step(span / 6.0)
    for mk in np.arange(0.0, span + 1e-9, step):
        j = int(np.argmin(np.abs(ts - mk)))
        ax.scatter([ts[j]], [turns[j]], s=66, color="#EF6C00",
                   edgecolor="white", lw=1.4, zorder=4)
    ax.scatter([ts[0]], [turns[0]], s=66, color="#EF6C00", edgecolor="white", lw=1.4, zorder=4)
    ymax = float(turns[-1]) or 1.0
    ax.set_xlim(-0.02 * span, 1.04 * span)
    ax.set_ylim(-0.17 * ymax, 1.06 * ymax)  # reserve a clean band below the curve for the note
    ax.set_yticks([y for y in ax.get_yticks() if y >= -1e-9])  # no negative "turns completed" ticks
    ax.set_xlabel("time since it started turning (s)")
    ax.set_ylabel("turns completed")
    ax.grid(alpha=0.3, zorder=0)
    # Motion-aware one-line reading, printed ON the figure so the picture and the caption can
    # never disagree (A4: the old caption asserted "grows steadily with time" on a decel clip).
    note = {
        "decelerating": "the line climbs steeply, then bends flatter — fewer turns each "
                        "second, so it is slowing down",
        "accelerating": "the line climbs ever more steeply — more turns each second, so it "
                        "is speeding up",
        "uniform": "the line is straight — the same number of turns each second, a steady spin",
    }.get(mt, "")
    if note:
        ax.text(0.5, 0.03, note, transform=ax.transAxes, ha="center", va="bottom",
                fontsize=9.5, color="#37474F", fontweight="bold", wrap=True,
                bbox=dict(fc="white", ec="#90A4AE", alpha=0.92, boxstyle="round,pad=0.3"))
    ax.set_title(_title(scene, "How many turns as time passes"))
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
                 hline=None, hline_lbl=None, smooth_trend=False, note=None,
                 uncorrected_col=None, magnitude=False):
    t = cols.get("time_s")
    y = cols.get(col)
    # `magnitude` — plot the SPEED, not the tracker's signed value. theta = atan2 in image
    # coordinates, so a clip filmed from the other side records omega negative: both ceiling
    # fans run -11.6 -> -1.0 rad/s for a coast-DOWN. Everything else on this figure had already
    # been resolved to a magnitude (the "clip average" line via canonical_omega, the phase-band
    # words via |omega|) while the curve alone stayed signed — so fan-4028 shipped an average
    # line at +5.70 floating above a curve that never rose above -1, inside a band labelled
    # "increasing" where the curve visibly fell. The sign is not physics a reader needs; which
    # way it goes round is carried by the arrows and by the word in the prose.
    if magnitude:
        y = np.abs(np.asarray(y, dtype=float)) if y is not None else y
    labels = stats.get("phases", {}).get("phase_labels") or []
    if not _phases_trustworthy(stats, labels):  # non-uniform clip mislabelled all-STABLE
        labels = []
    fig, ax = plt.subplots(figsize=(8, 5))
    # Pass the series itself: a phase word must be checkable against the curve it sits over.
    _shade_phases(ax, t, labels, y=y)
    # Where we adjust a curve, draw BOTH: the measurement as it came off the video, and what
    # we corrected it to. The honesty box used to have to make that argument in prose while
    # the figure beside it drew a single confident line — and the figure is what a student
    # looks at. Two adjustments qualify, and each names itself in the legend.
    pre = cols.get(uncorrected_col) if uncorrected_col else None
    if pre is not None and magnitude:
        pre = np.abs(np.asarray(pre, dtype=float))
    if pre is not None and np.isfinite(np.asarray(pre, float)).any():
        # (1) The camera-angle correction. The clip was filmed at a slant, so the object
        # appears to race and stall once per turn; that is the camera position, not the object.
        # Neutral grey for the "before": it has to be legible enough to read the ripple off,
        # but it must never compete with the coloured curve that IS the measurement.
        ax.plot(t, pre, color="#78909C", lw=0.9, alpha=0.9, zorder=2,
                label="what came off the video")
        ax.plot(t, y, color=colour, lw=2.0, zorder=3,
                label="after correcting for the camera angle")
        ax.legend(fontsize=8, loc="best")
    elif smooth_trend:
        # (2) A diagnosed per-revolution artifact on a clip long enough to average it out:
        # the raw values faint, the one-revolution average bold (the real physics).
        ax.plot(t, y, color=colour, lw=0.8, alpha=0.30, label="what we measured")
        ax.plot(t, _smooth_1rev(t, y, stats), color=colour, lw=2.6,
                label="after averaging over one turn")
        ax.legend(fontsize=8, loc="best")
    else:
        ax.plot(t, y, color=colour, lw=1.6)
    if note:
        # Used when the within-revolution detail could not be VERIFIED (too few revolutions)
        # rather than diagnosed. Smoothing is not the answer there: the 1-revolution window is
        # a large fraction of a short record, so it flattens the real transient — on
        # turntable-3 it cut a genuine 1.44 m/s flick peak to 1.09. Keep the measurement and
        # mark it instead.
        ax.text(0.5, -0.155, note, transform=ax.transAxes, ha="center", va="top",
                fontsize=7.5, color="#B5651D", style="italic", wrap=True)
    if hline is not None and np.isfinite(hline):
        ax.axhline(hline, ls="--", color="#455A64", lw=1.2,
                   label=hline_lbl or None)
        if hline_lbl:
            ax.legend(fontsize=8, loc="best")
    ax.set_xlabel("time (s)")
    ax.set_ylabel(ylabel)
    ax.set_title(_title(scene, what))
    fig.tight_layout()
    fig.savefig(PLOTS / name)
    plt.close(fig)


def fig_annotated_table(stats, scene):
    # Mirror the student-facing typeset Table 1: the same six quantities, clip-average labelled
    # to match the honesty box, no internal-only rows (std radius, max/stable a_c, the mean-vs-
    # fitted radius pair) and unit "m/s²" not "m/s^2" (C4 — this artifact used to leak pipeline
    # vocabulary and a "Stable centripetal accel." 8.55 the student's table never shows).
    s, pf, cal = stats["summary"], stats["period_and_frequency"], stats["calibration"]
    omega_val, omega_is_clip_avg = canonical_omega(stats)
    avg = " (clip avg)" if omega_is_clip_avg else ""
    rows = [
        ("Radius", _fmt(cal.get("r_fit_m") or s.get("mean_r_m"), 3), "m"),
        ("Angular velocity" + avg, _fmt(omega_val, 2), "rad/s"),
        ("Centripetal acceleration" + avg, _fmt(s.get("mean_ac"), 2), "m/s²"),
        ("Tangential speed", _fmt(s.get("mean_v"), 2), "m/s"),
        ("Period", _fmt(pf.get("period_s"), 2), "s"),
        ("Frequency", _fmt(pf.get("frequency_hz"), 2), "Hz"),
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
    fps = (stats.get("video_info") or {}).get("fps") or 30.0
    friendly = {"INCREASE": "speeding up", "STABLE": "steady", "DECREASE": "slowing down"}
    seq = []
    for s, e, lab in _phase_spans(labels):
        L = str(lab).upper()
        if L in ("INACTIVE", "IDLE"):
            continue
        if not _phase_significant((e - s) / fps):       # skip a 1-2 frame despeckle sliver
            continue                                     # (so prose can't claim a phantom "steady")
        if not seq or seq[-1]["label"] != L.lower():
            # `meaning` describes the MOTION (what the prose talks about); `figure_word` is what the
            # band literally prints, which describes the plotted QUANTITY. Recording both keeps the
            # Axis-4 judge from reading "speeding up" in the prose vs "increasing" on the figure as
            # a contradiction.
            seq.append({"label": L.lower(), "meaning": friendly.get(L, L.lower()),
                        "figure_word": PHASE_WORDS.get(L, L.lower())})
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
                    "target": "double-headed arrow from the centre out to the circular path"})
    # ω/a_c/v are clip averages on a (de)accelerating clip — tag "(avg)" to match the callout (C3),
    # so the prose that quotes these EXACT values inherits the qualifier too.
    avg = " (avg)" if _oca else ""
    v_m_s = (stats.get("summary") or {}).get("mean_v")
    if v_m_s is not None:
        img.append({"label": "linear speed", "symbol": "v", "value": _fmt(v_m_s, 2, "m/s") + avg,
                    "target": "straight arrow at the object, along the direction it travels"})
    if omega_val is not None:
        img.append({"label": "angular speed", "symbol": "ω",
                    "value": _fmt(abs(omega_val), 2, "rad/s") + avg,
                    "target": "small curved arrow showing which way it turns"})
    a_c = (stats.get("summary") or {}).get("mean_ac")
    if a_c is not None:
        img.append({"label": "centripetal acceleration", "symbol": "a_c",
                    "value": _fmt(a_c, 2, "m/s²") + avg,
                    "target": "straight arrow from the object pointing inward toward the centre"})
    if img:
        # Says WHAT is marked, not HOW it is drawn. The layout detail lives in each annotation's
        # `target` (where the Axis-4 judge needs it); spelling it out here put the drawing mechanics
        # in front of the material writer, which came back as "each annotated with its symbol" —
        # and `annotate` is banned student-facing vocabulary, so the tier gate rejected it.
        man["annotated_image.png"] = {
            "shows": "photo of the object with the fitted circle, and the radius, linear speed, "
                     "angular speed and centripetal acceleration each marked with its symbol "
                     "and value",
            "annotations": img}
    if r_m is not None:
        # The basic frame now carries the SAME four marks, named in words and quoting only the two
        # values that tier may meet (the radius, and the turn rate as turns per second — never
        # rad/s, never an acceleration value). Keep this list in step with the `plain=True` branch
        # of fig_annotated_image: the material writer describes the overlays from HERE, so a
        # manifest that still promises "just the radius" makes the prose contradict the picture.
        basic_ann = [{"label": "how far out it sits from the centre", "value": _fmt(r_m, 3, "m"),
                      "target": "double-headed arrow from the centre out to the circular path"},
                     {"label": "how fast it travels along the circle",
                      "target": "straight arrow at the object, along the direction it travels"},
                     {"label": "the inward pull that keeps it on the circle",
                      "target": "straight arrow from the object pointing inward toward the centre"}]
        f_hz = (stats.get("period_and_frequency") or {}).get("frequency_hz")
        basic_ann.insert(2, {
            "label": "how fast it sweeps round the centre",
            **({"value": f"about {_fmt(f_hz, 2)} turns each second"}
               if isinstance(f_hz, (int, float)) else {}),
            "target": "small curved arrow showing which way it turns"})
        man["annotated_image_basic.png"] = {
            "shows": "the same photo of the object on its circular path, with how far out it "
                     "sits, how fast it travels along the circle, how fast it sweeps round, and "
                     "the inward pull each marked and named in words (no symbols)",
            "annotations": basic_ann}

    # The basic "turns completed vs time" curve. Described qualitatively (no numbers to quote)
    # so its narration is driven by the grounded motion type, and by the SHAPE the render draws:
    # bending flatter = slowing, steepening = speeding up, straight = steady (C5/A4). Gated on a
    # turning window being present (angle milestones exist), matching when the figure is drawn.
    try:
        seed = json.loads((DATA / "material_seed.json").read_text())
        if seed.get("angle_milestones"):
            shape = {"decelerating": "the line bends flatter over time, so it is slowing down",
                     "accelerating": "the line steepens over time, so it is speeding up"}.get(
                         (seed.get("angular_acceleration") or {}).get("motion_type"),
                         "a straight line, so it turns at a steady rate")
            man["angle_points_basic.png"] = {
                "shows": "a graph of how many turns the object has completed as time passes; "
                         + shape}
    except Exception:  # noqa: BLE001 — the manifest is best-effort provenance, never fatal
        pass

    phases = _phase_sequence(stats)
    for fig in ("omega_t.png", "annotated_graph.png"):
        man[fig] = {"shows": "angular speed over time"}
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

    # When the per-instant omega ripple cannot be presented as physics, the omega(t)/a_c(t)
    # plots show the 1-revolution trend (bold) over a faint raw trace. Data/stats are
    # unchanged — only the plotted curve is smoothed.
    #
    # This covers BOTH reasons the trust channel withholds per-instant omega: a ripple we
    # have diagnosed (`_unreliable`) and one we could not assess because the clip is under
    # two revolutions (`_unverified`). Keying only on the first left the prose saying the
    # timeline could not be trusted while the figure beside it drew that same timeline as a
    # confident line — and the figure is what a student looks at.
    diagnosed = unverified = False
    per_instant_note = None
    try:
        from .. import quality_signals
        sig = quality_signals.compute(DATA / "kinematics.csv", stats)
        flags = sig.get("flags", [])
        diagnosed = "per_instant_omega_unreliable" in flags
        unverified = "per_instant_omega_unverified" in flags
        if unverified:
            per_instant_note = (
                f"Within-revolution detail is not verified: this clip covers only "
                f"{sig.get('n_revolutions')} revolutions, too few to tell a measurement "
                f"artifact from real motion. The trend across the clip is sound.")
    except Exception:
        diagnosed = unverified = False

    s, st, pf = stats["summary"], stats["stable_phase"], stats["period_and_frequency"]
    # The ω(t) reference line matches the table/prose: clip-average on a (de)accelerating
    # clip (labelled so), the stable-phase mean only on a genuinely uniform spin.
    stable_omega, _omega_is_clip_avg = canonical_omega(stats)
    omega_hline_lbl = "clip average" if _omega_is_clip_avg else "stable mean"
    mean_r = s.get("mean_r_m")
    # The a_c(t) reference line must match the typeset Table 1 the student reads (A5): that
    # table shows the clip-average a_c (summary.mean_ac). On a (de)accelerating clip use that
    # average, labelled "clip average"; the stable-phase mean (stable_mean_ac, ~8.55 on the
    # flick) is only meaningful — and only matches the table — for a genuinely uniform spin,
    # where it equals the average anyway. Mirrors the ω(t) clip-average/stable-mean choice.
    ac_hline = s.get("mean_ac") if _omega_is_clip_avg else st.get("stable_mean_ac")
    ac_hline_lbl = "clip average" if _omega_is_clip_avg else "stable mean"

    fig_annotated_image(stats, scene, cols)
    fig_annotated_image_basic(stats, scene, cols)  # same frame, worded labels (basic tier)
    traj_x, traj_y = fig_trajectory(stats, cols, scene)
    fig_trajectory_basic(stats, cols, scene)  # single-colour path for the basic tier
    fig_angle_points_basic(stats, cols, scene, unreliable=diagnosed)  # angle-at-time dots
    # ω(t) with phase bands == the "annotated graph"
    # On a clip whose camera angle was corrected, kinematics.csv carries the pre-correction
    # series too — the ω(t) and a_c(t) plots then draw the measurement and the correction
    # together. a_c is where the difference is largest, because it follows ω squared.
    _series_plot("annotated_graph.png", cols, stats, scene, "omega_rad_s",
                 "angular speed (rad/s)", "Angular speed & phases",
                 TRACE["omega"], hline=stable_omega, hline_lbl=omega_hline_lbl,
                 smooth_trend=diagnosed, note=per_instant_note,
                 uncorrected_col="omega_rad_s_uncorrected", magnitude=True)
    _series_plot("omega_t.png", cols, stats, scene, "omega_rad_s",
                 "angular speed (rad/s)", "Angular speed", TRACE["omega"],
                 hline=stable_omega, hline_lbl=omega_hline_lbl, smooth_trend=diagnosed,
                 note=per_instant_note, uncorrected_col="omega_rad_s_uncorrected",
                 magnitude=True)
    _series_plot("ac_t.png", cols, stats, scene, "ac_m_s2",
                 "centripetal acceleration (m/s^2)", "Centripetal acceleration",
                 TRACE["ac"], hline=ac_hline, hline_lbl=ac_hline_lbl,
                 smooth_trend=diagnosed, note=per_instant_note,
                 uncorrected_col="ac_m_s2_uncorrected")
    _series_plot("radius_t.png", cols, stats, scene, "r_m",
                 "radius (m)", "Orbit radius", TRACE["r"], hline=mean_r,
                 hline_lbl="mean", smooth_trend=diagnosed, note=per_instant_note)
    _series_plot("theta_t.png", cols, stats, scene, "theta_rad",
                 "angle (rad)", "Unwrapped angle", TRACE["theta"])
    _series_plot("v_t.png", cols, stats, scene, "v_m_s",
                 "tangential speed (m/s)", "Tangential speed", TRACE["v"],
                 hline=s.get("mean_v"), hline_lbl="mean", smooth_trend=diagnosed, note=per_instant_note)
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
