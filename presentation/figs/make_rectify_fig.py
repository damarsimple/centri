#!/usr/bin/env python3
"""Regenerates `rect4046_slide.png` for the weekly deck from a real pipeline run.

Kept in the repo deliberately: the technical report's figures lost their one-off
generators and had to be force-added as PNGs because they were the only copy.

Reads the shipped run (not the prototype) so the deck states what the system does:
static detected axle, ripple CV 0.096 -> 0.033, radial residual 5.22% -> 3.42%.

    python3 presentation/figs/make_rectify_fig.py [workspace_dir]
"""
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
WS = Path(sys.argv[1]) if len(sys.argv) > 1 else (
    REPO / "agent-backend/workspaces/job_roundabout-4046-final")
OUT = Path(__file__).resolve().parent / "rect4046_slide.png"

# Deck house palette; validated as a categorical pair (protan dE 21.2, all checks pass).
C_FILMED = "#C62828"
C_FIXED = "#1F6FB2"
INK = "#1a1a1a"
MUTED = "#616161"
GRID = "#d8d8d8"

D = WS / "analysis_output/data"
stats = json.loads((D / "stats.json").read_text())
pi = json.loads((D / "pipeline_inputs.json").read_text())
rect = stats["calibration"]["rectification"]
fps = stats["video_info"]["fps"]
y_off = float(stats["roi_crop"].get("y_off", 0) or 0)

rows = [l.split(",") for l in (D / "kinematics.csv").read_text().splitlines()]
hdr, rows = rows[0], rows[1:]
col = {k: i for i, k in enumerate(hdr)}


def series(name):
    return np.array([float(r[col[name]]) if r[col[name]] not in ("", "nan") else np.nan
                     for r in rows])


t = series("time_s")
om_fixed = np.abs(series("omega_rad_s"))
x, y = series("x_px"), series("y_px")          # IMAGE space, as filmed

# "as filmed" omega: the same recipe the pipeline uses, but measured in raw image
# pixels about the imaged axle — i.e. what the numbers look like without the un-projection.
hub = pi["hub_px"]
hx, hy = float(hub[0]), float(hub[1]) - y_off
m = np.isfinite(x) & np.isfinite(y)
w = max(11, 2 * (int(fps) // 6) + 1)
w += (w % 2 == 0)
om_filmed = np.full(len(t), np.nan)
# Per CONTIGUOUS run of tracked frames, exactly as kinematics._segmented does. Smoothing
# or differentiating straight across a dropout invents a huge slope at the seam — the
# spikes that appear if you take the whole series at once are that artefact, not the clip.
lab, n_seg = scipy.ndimage.label(m)
for s in range(1, n_seg + 1):
    idx = np.flatnonzero(lab == s)
    if idx.size < w + 2:
        continue
    thseg = np.unwrap(np.arctan2(y[idx] - hy, x[idx] - hx))
    thseg = savgol_filter(thseg, w, 3)
    om_filmed[idx] = np.abs(scipy.ndimage.median_filter(
        np.gradient(thseg, t[idx]), size=max(5, int(fps // 10)), mode="nearest"))

fig, ax = plt.subplots(1, 3, figsize=(13.6, 4.15),
                       gridspec_kw={"width_ratios": [1.75, 1.0, 0.82]})

# ---- left: the turn rate, as filmed vs corrected --------------------------------
a = ax[0]
a.plot(t, om_filmed, lw=1.1, color=C_FILMED, label="as filmed")
a.plot(t, om_fixed, lw=2.0, color=C_FIXED, label="corrected for the camera angle")
a.set_xlabel("time (seconds)", color=INK)
a.set_ylabel("turn rate  |ω|  (radians / second)", color=INK)
a.set_title("The wheel slows smoothly. Only one of these lines says so.",
            color=INK, fontsize=11.0, pad=10)
a.grid(alpha=0.5, color=GRID, lw=0.7)
a.set_axisbelow(True)
for s in ("top", "right"):
    a.spines[s].set_visible(False)
for s in ("left", "bottom"):
    a.spines[s].set_color(MUTED)
a.tick_params(colors=MUTED, labelsize=9)
leg = a.legend(loc="upper right", frameon=False, fontsize=9.5)
for txt in leg.get_texts():
    txt.set_color(INK)
# direct labels as the secondary encoding, so identity is never colour-alone
pk_t = 3.05
pk_v = float(np.nanmax(om_filmed[(t > 2.8) & (t < 3.3)]))
# Axes-fraction placement: data coords put this outside the axes and it collided with the title.
a.annotate("one false swing for every\nturn of the wheel", xy=(pk_t, pk_v),
           xytext=(0.30, 0.90), textcoords="axes fraction",
           fontsize=9.0, color=MUTED, ha="left",
           arrowprops=dict(arrowstyle="->", color=MUTED, lw=0.9,
                           connectionstyle="arc3,rad=-0.2"))

# ---- right: why — the axle is not the centre of the imaged path ------------------
b = ax[1]
b.plot(x[m], y[m], ".", ms=1.7, color=C_FILMED, alpha=0.5)
ec = rect["ellipse_centre_px"]
b.set_aspect("equal")
b.invert_yaxis()
b.set_xticks([])
b.set_yticks([])
for s in ("top", "right", "left", "bottom"):
    b.spines[s].set_color(GRID)
b.set_title("Seen at a slant, the axle leaves the centre", color=INK,
            fontsize=11.0, pad=10)
b.text(0.5, -0.03, "the handle's path, as filmed", transform=b.transAxes,
       ha="center", va="top", fontsize=9.0, color=C_FILMED)

# The gap is ~85 px on a ~1000 px orbit — invisible at this scale, so the third panel
# magnifies it. A box here marks what that panel shows.
pad = 115.0
x0, x1 = min(hx, ec[0]) - pad, max(hx, ec[0]) + pad
y0, y1 = min(hy, ec[1]) - pad, max(hy, ec[1]) + pad
b.add_patch(plt.Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, ec=MUTED, lw=1.0))

# ---- right: that centre region, magnified ---------------------------------------
c = ax[2]
c.set_xlim(x0, x1)
c.set_ylim(y1, y0)                                   # inverted, like the video frame
c.set_aspect("equal")
c.set_xticks([])
c.set_yticks([])
for s in c.spines.values():
    s.set_color(GRID)
c.annotate("", xy=(ec[0], ec[1]), xytext=(hx, hy),
           arrowprops=dict(arrowstyle="<->", color=INK, lw=1.6))
c.plot([ec[0]], [ec[1]], "o", ms=12, mfc="none", mec=INK, mew=1.9)
c.plot([hx], [hy], "P", ms=14, color=C_FIXED, mec="white", mew=1.3)
c.text(ec[0] + 16, ec[1] - 16, "centre of the\npath we see", fontsize=9.2,
       color=INK, ha="left", va="bottom")
c.text(hx + 16, hy + 18, "the real axle", fontsize=9.2, color=C_FIXED,
       ha="left", va="top")
c.text(0.5, 0.06, f"{rect['hub_offset_px']:.0f} px apart", transform=c.transAxes,
       ha="center", fontsize=11.0, color=INK)
c.set_title("Magnified: the gap that causes it", color=INK,
            fontsize=11.0, pad=10)

fig.tight_layout(rect=[0, 0.01, 1, 0.995])
fig.savefig(OUT, dpi=170, facecolor="white")
print(f"wrote {OUT}")
print(f"  hub offset {rect['hub_offset_px']:.1f} px, tilt {rect['tilt_deg']:.1f} deg, "
      f"radial residual {rect['radial_residual_before_pct']:.2f}% -> "
      f"{rect['radial_residual_after_pct']:.2f}%")
print(f"  mean |omega| as filmed {np.nanmean(om_filmed):.4f} -> corrected "
      f"{np.nanmean(om_fixed):.4f} rad/s")
