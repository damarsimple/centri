#!/usr/bin/env python3
"""Regenerates `fig-rectify-4046.png` from a real pipeline run.

Kept in the repo on purpose: this report's first-generation figures were produced by
one-off scripts that were not saved, so the PNGs became the only copy and had to be
force-added past the repo-wide *.png rule. This one rebuilds from any completed run.

Shows the SHIPPED implementation (analysis/rectify.py: static detected axle, no
camera-drift removal), not the prototype, so the figure and the pipeline agree.

    python3 technical-report/figures/make_fig_rectify_4046.py [workspace_dir]
"""
import csv
import json
import sys
from pathlib import Path

import numpy as np
import scipy.ndimage
from scipy.signal import savgol_filter
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "agent-backend/workspace_lib"))

WS = Path(sys.argv[1]) if len(sys.argv) > 1 else (
    REPO / "agent-backend/workspaces/job_roundabout-4046-final")
OUT = Path(__file__).resolve().parent / "fig-rectify-4046.png"

C_BASE = "#C62828"      # as filmed
C_RECT = "#1F6FB2"      # rectified
INK, MUTED, GRID = "#1a1a1a", "#616161", "#d8d8d8"

D = WS / "analysis_output"
stats = json.loads((D / "data/stats.json").read_text())
pi = json.loads((D / "data/pipeline_inputs.json").read_text())
rect = stats["calibration"]["rectification"]
fps = stats["video_info"]["fps"]
y_off = float(stats["roi_crop"].get("y_off", 0) or 0)

rows = list(csv.DictReader(open(D / "data/kinematics.csv")))
col = lambda k: np.array([float(r[k]) if r[k] not in ("", "nan") else np.nan for r in rows])
t, x, y = col("time_s"), col("x_px"), col("y_px")
om_rect, r_rect = np.abs(col("omega_rad_s")), col("r_px")
hx, hy = float(pi["hub_px"][0]), float(pi["hub_px"][1]) - y_off
m = np.isfinite(x) & np.isfinite(y)


def omega_about(cx, cy):
    """The pipeline's own smoothing recipe, per contiguous run of tracked frames.
    Differentiating across a dropout invents a slope at the seam."""
    out = np.full(len(t), np.nan)
    w = max(11, 2 * (int(fps) // 6) + 1)
    w += (w % 2 == 0)
    lab, n = scipy.ndimage.label(m)
    for s in range(1, n + 1):
        idx = np.flatnonzero(lab == s)
        if idx.size < w + 2:
            continue
        th = savgol_filter(np.unwrap(np.arctan2(y[idx] - cy, x[idx] - cx)), w, 3)
        out[idx] = np.abs(scipy.ndimage.median_filter(
            np.gradient(th, t[idx]), size=max(5, int(fps // 10)), mode="nearest"))
    return out


# the report's deliberately-generous baseline: best least-squares circle, not the axle
M = np.c_[2 * x[m], 2 * y[m], np.ones(m.sum())]
sol, *_ = np.linalg.lstsq(M, x[m] ** 2 + y[m] ** 2, rcond=None)
cx0, cy0 = sol[0], sol[1]
om_base = omega_about(cx0, cy0)

fig, ax = plt.subplots(1, 3, figsize=(15.0, 4.3), gridspec_kw={"width_ratios": [1.9, 1.0, 1.0]})

a = ax[0]
a.plot(t, om_base, lw=1.0, color=C_BASE, label="baseline (best-fit circle, as filmed)")
a.plot(t, om_rect, lw=1.9, color=C_RECT, label="projectively rectified (as shipped)")
a.set_xlabel("time (s)", color=INK)
a.set_ylabel(r"$|\omega|$  (rad/s)", color=INK)
a.set_title(r"$\omega(t)$: the wheel coasts smoothly; the ripple is projection",
            color=INK, fontsize=11, pad=9)
a.grid(alpha=.5, color=GRID, lw=.7)
a.set_axisbelow(True)
for s in ("top", "right"):
    a.spines[s].set_visible(False)
for s in ("left", "bottom"):
    a.spines[s].set_color(MUTED)
a.tick_params(colors=MUTED, labelsize=9)
leg = a.legend(loc="upper right", frameon=False, fontsize=9)
for txt in leg.get_texts():
    txt.set_color(INK)
a.annotate("one oscillation per revolution", xy=(3.0, np.nanmax(om_base[(t > 2.7) & (t < 3.3)])),
           xytext=(0.30, 0.90), textcoords="axes fraction", fontsize=9, color=MUTED,
           arrowprops=dict(arrowstyle="->", color=MUTED, lw=.9,
                           connectionstyle="arc3,rad=-0.2"))

b = ax[1]
b.plot(x[m], y[m], ".", ms=1.6, color=C_BASE, alpha=.5)
ec = rect["ellipse_centre_px"]
b.plot([ec[0]], [ec[1]], "o", ms=9, mfc="none", mec=INK, mew=1.7)
b.plot([hx], [hy], "P", ms=11, color=C_RECT, mec="white", mew=1.2)
b.annotate("", xy=(ec[0], ec[1]), xytext=(hx, hy),
           arrowprops=dict(arrowstyle="<->", color=INK, lw=1.4))
b.text(hx + 30, (hy + ec[1]) / 2, f"{rect['hub_offset_px']:.0f} px", fontsize=9.5, color=INK,
       va="center")
b.set_aspect("equal")
b.invert_yaxis()
b.set_xticks([]); b.set_yticks([])
for s in b.spines.values():
    s.set_color(GRID)
b.set_title("as filmed: an ellipse, and the axle (+)\nis not its centre (o)",
            color=INK, fontsize=11, pad=9)

c = ax[2]
th = np.linspace(0, 2 * np.pi, 400)
rr = r_rect[np.isfinite(r_rect)]
c.plot(rr.mean() * np.cos(th), rr.mean() * np.sin(th), lw=1.0, color=MUTED, alpha=.6)
ang = np.arctan2(y[m] - hy, x[m] - hx)
c.plot(r_rect[m] * np.cos(ang), r_rect[m] * np.sin(ang), ".", ms=1.6, color=C_RECT, alpha=.55)
c.set_aspect("equal")
c.invert_yaxis()
c.set_xticks([]); c.set_yticks([])
for s in c.spines.values():
    s.set_color(GRID)
c.set_title(f"rectified: a circle to within\n{rect['radial_residual_after_pct']:.2f}%",
            color=INK, fontsize=11, pad=9)

fig.tight_layout(rect=[0, 0.01, 1, 0.995])
fig.savefig(OUT, dpi=165, facecolor="white")
print(f"wrote {OUT}")
print(f"  hub offset {rect['hub_offset_px']:.1f} px | tilt {rect['tilt_deg']:.1f} deg | "
      f"residual {rect['radial_residual_before_pct']:.2f}% -> {rect['radial_residual_after_pct']:.2f}%")
print(f"  mean |omega| baseline {np.nanmean(om_base):.3f} -> rectified {np.nanmean(om_rect):.3f} rad/s")
