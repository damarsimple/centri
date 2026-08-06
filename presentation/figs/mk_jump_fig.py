#!/usr/bin/env python3
"""Deck figure: turntable-3's inward-pull spikes are tracker jumps, not motion.

Reads the DELIVERED kinematics for turntable-3 and marks every frame where the tracked marker
moves far further than its own neighbourhood allows. Detection is deliberately speed-adaptive
(step vs the local median step, not a fixed pixel threshold): computerfan-4029 legitimately moves
~240 px between frames at peak speed, so any absolute cut-off would either miss turntable-3's
jumps or condemn the fan's real motion.

The data source is a workspace that has since been ARCHIVED — turntable-3 was withdrawn from the
corpus on 2026-08-06 for these very jumps — so the path is resolved live-or-archive below. The
numbers this script prints are also written into the caption of the slide that uses it, and the
resulting PNG is committed. If the workspace is gone entirely this fails loudly, naming both
places it looked, rather than silently drawing something else.

Run:  python3 mk_jump_fig.py
"""
import csv
import pathlib

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = pathlib.Path(__file__).resolve().parent


def find_workspace(job: str, must_contain: str = "") -> pathlib.Path:
    """The job directory, live or archived, that actually holds `must_contain`.

    Workspaces move to `workspaces-archive/<batch>/` once a clip is superseded or withdrawn —
    turntable-3 was withdrawn 2026-08-06 — so a bare `workspaces/<job>` path stops resolving.
    Several batches can hold a directory of the same name (a failed run, a pre-fix snapshot, the
    withdrawn shipped run), and only some carry the outputs, so require the file we came for and
    skip candidates that lack it. Live wins over archived; otherwise newest batch first.
    """
    base = pathlib.Path("/home/damar/centri/agent-backend")
    cands = [base / "workspaces" / job]
    arch = base / "workspaces-archive"
    if arch.is_dir():
        cands += [sub / job for sub in sorted(arch.iterdir(), reverse=True) if sub.is_dir()]
    seen = [c for c in cands if c.is_dir()]
    for c in seen:
        if not must_contain or (c / must_contain).exists():
            return c
    raise SystemExit(
        f"{job}"
        + (f"/{must_contain}" if must_contain else "")
        + " not found. Looked in: "
        + ", ".join(str(c) for c in cands[:6])
        + (f" ({len(seen)} dir(s) matched the name but lacked the file)" if seen else ""))
CSV = find_workspace("job_turntable-3", "analysis_output/data/kinematics.csv") \
    / "analysis_output" / "data" / "kinematics.csv"
WIN, K, FLOOR = 15, 8.0, 50.0          # jump = step > max(K x local median, FLOOR px)
SMOOTH_HALFWIN = 12                     # Savitzky-Golay smears a step this far either side


def load():
    rows = list(csv.DictReader(CSV.open()))
    out = {}
    for k in rows[0]:
        v = []
        for r in rows:
            try:
                v.append(float(r[k]))
            except (TypeError, ValueError):
                v.append(np.nan)
        out[k] = np.asarray(v)
    return out


def find_jumps(step):
    hits = []
    for i in range(len(step)):
        if not np.isfinite(step[i]):
            continue
        lo, hi = max(0, i - WIN), min(len(step), i + WIN + 1)
        nb = np.concatenate([step[lo:i], step[i + 1:hi]])
        nb = nb[np.isfinite(nb)]
        if len(nb) >= 5 and step[i] > max(K * max(np.median(nb), 1e-6), FLOOR):
            hits.append(i)
    return hits


def main():
    if not CSV.exists():
        raise SystemExit(f"missing {CSV} — the committed PNG "
                         "beside this script is the record")
    c = load()
    t, ac, x, y = c["time_s"], c["ac_m_s2"], c["x_px"], c["y_px"]
    active = c["active"] > 0.5
    step = np.hypot(np.diff(x), np.diff(y))
    jumps = find_jumps(step)

    bad = np.zeros(len(t), bool)
    for i in jumps:
        bad[max(0, i - SMOOTH_HALFWIN): i + SMOOTH_HALFWIN + 1] = True
    clean = active & ~bad
    mean_shipped, mean_clean = np.nanmean(ac[active]), np.nanmean(ac[clean])

    fig, ax = plt.subplots(figsize=(8.4, 4.3))
    for i in jumps:                                   # the contaminated windows
        ax.axvspan(t[max(0, i - SMOOTH_HALFWIN)], t[min(len(t) - 1, i + SMOOTH_HALFWIN)],
                   color="#C62828", alpha=0.10, lw=0)
    ax.plot(t, ac, color="#E53935", lw=1.8, zorder=3)
    ax.axhline(mean_shipped, ls="--", color="#455A64", lw=1.3,
               label=f"mean as shipped — {mean_shipped:.2f} m/s²")
    ax.axhline(mean_clean, ls=":", color="#2E7D32", lw=1.8,
               label=f"mean with the jumps removed — {mean_clean:.2f} m/s²")
    # Headroom first, then stagger the callouts — at equal height they collide with each other
    # and with the title, which reads as a broken figure rather than a labelled one.
    top = np.nanmax(ac[active]) * 1.45
    ax.set_ylim(top=top)
    for n, i in enumerate(jumps):
        ax.annotate(f"{step[i]:.0f} px in one frame",
                    xy=(t[i], np.nanmax(ac[max(0, i - 8):i + 9])),
                    xytext=(t[i], top * (0.94, 0.72, 0.83)[n % 3]),
                    ha="center", fontsize=8, color="#C62828", fontweight="bold",
                    bbox=dict(fc="white", ec="#C62828", alpha=0.9, boxstyle="round,pad=0.2"),
                    arrowprops=dict(arrowstyle="-", color="#C62828", lw=1.0))
    ax.set_xlabel("time (s)")
    ax.set_ylabel("inward pull $a_c$ (m/s²)")
    ax.set_title("turntable-3 — every spike is a tracker jump, not motion", fontsize=11)
    ax.legend(fontsize=8, loc="upper right")
    ax.grid(alpha=0.25, ls="--")
    fig.tight_layout()
    fig.savefig(HERE / "jump_tt3.png", dpi=160)

    print(f"jumps at t = {[round(float(t[i]), 3) for i in jumps]}")
    print(f"displacements = {[round(float(step[i])) for i in jumps]} px "
          f"(median step {np.median(step[np.isfinite(step)]):.1f} px)")
    print(f"active samples {active.sum()}, contaminated {(active & bad).sum()}")
    print(f"mean a_c shipped {mean_shipped:.3f} -> jump-free {mean_clean:.3f} "
          f"({100 * (mean_shipped - mean_clean) / mean_clean:+.1f}%)")
    print(f"max a_c shipped {np.nanmax(ac[active]):.2f} -> jump-free "
          f"{np.nanmax(ac[clean]):.2f}; worst rest-band spike {np.nanmax(ac[~active]):.2f}")
    print("wrote jump_tt3.png")


if __name__ == "__main__":
    main()
