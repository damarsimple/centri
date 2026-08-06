"""Figure for the 07-23 plan deck: show the measurement AND the correction on one axis.

Real before/after on the playground-wheel clip (roundabout-4046):
  before = the archived run, carrying the coordinate error and no angle correction
  after  = the shipped run, coordinate-fixed and un-projected for the camera angle
Both are the SAME video; only the processing differs. Plots inward acceleration a_c,
where the difference is amplified because a_c goes as omega squared.
"""
import csv
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BEFORE = ("/home/damar/centri/agent-backend/workspaces-archive/"
          "pre-coordfix-20260721-145038/job_roundabout-4046-r4/analysis_output/data/kinematics.csv")
# Both sides are pinned to ARCHIVED runs on purpose. This is a before/after figure: if the
# "after" tracked whatever is live, a later corpus regeneration would silently redraw it and the
# slide would stop showing the change it claims to show. Archived 2026-07-29.
AFTER = ("/home/damar/centri/agent-backend/workspaces-archive/pre-full-e2e-20260729/job_roundabout-4046-final"
         "/analysis_output/data/kinematics.csv")
OUT = "/home/damar/centri/presentation/figs/wheel-ac-corrected.png"

C_MEAS, C_APP, C_ACC, C_GREY = "#1F6FB2", "#2E7D32", "#C62828", "#616161"
YTOP = 60.0


def load(path):
    rows = [r for r in csv.DictReader(open(path))
            if r["active"] in ("True", "true", "1") and r["ac_m_s2"] not in ("", "nan")]
    return (np.array([float(r["time_s"]) for r in rows]),
            np.array([float(r["ac_m_s2"]) for r in rows]))


tb, ab = load(BEFORE)
ta, aa = load(AFTER)

fig, ax = plt.subplots(figsize=(8.6, 4.3), dpi=200)
ax.plot(tb, ab, color=C_ACC, lw=1.2, alpha=0.85, zorder=2,
        label=f"what we measured   (average {ab.mean():.1f})")
ax.plot(ta, aa, color=C_MEAS, lw=1.8, zorder=3,
        label=f"after correcting for the camera angle   (average {aa.mean():.1f})")

# the raw curve leaves the top of the chart — say so rather than silently cropping it
n_off = int((ab > YTOP).sum())
ax.set_ylim(0, YTOP)
ax.text(0.5, 0.965, f"{n_off} points run off the top of this chart, the highest at "
                    f"{ab.max():.0f} m/s$^2$",
        transform=ax.transAxes, ha="center", va="top", fontsize=8.8, color=C_ACC, style="italic",
        bbox=dict(boxstyle="round,pad=0.28", fc="white", ec=C_ACC, lw=0.7, alpha=0.93), zorder=6)

ax.set_xlabel("time (s)")
ax.set_ylabel("inward acceleration (m/s$^2$)")
ax.set_title("Playground wheel: the same video, before and after correction", fontsize=11.5)
ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.20), ncol=2, fontsize=9.2,
          frameon=False)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
fig.tight_layout()
fig.savefig(OUT)
print(f"wrote {OUT} | before mean {ab.mean():.2f} max {ab.max():.1f} | "
      f"after mean {aa.mean():.2f} range {aa.min():.2f}-{aa.max():.2f} | off-scale {n_off}")
