"""Figure for the 07-23 plan deck: why a coasting-down fan is reported as 'speeding up'.

Plots fan-4028's angular velocity two ways from the SHIPPED kinematics.csv:
  - signed omega, which is what the constant-alpha fit runs on (negative all clip, rising to 0)
  - |omega|, the actual spin speed (falls from ~9.7 to ~1.8 rad/s)
The fit window is the coast-down side (impulsive_start=true), shaded.
"""
import csv, json
import pathlib

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


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

JOB = str(find_workspace("job_fan-4028-rect", "analysis_output/data/kinematics.csv")
          / "analysis_output" / "data")   # archived 2026-08-06
OUT = "/home/damar/centri/presentation/figs/fan-sign-4028.png"

C_MEAS, C_APP, C_ACC, C_GREY = "#1F6FB2", "#2E7D32", "#C62828", "#616161"

rows = [r for r in csv.DictReader(open(f"{JOB}/kinematics.csv"))
        if r["active"] in ("True", "true", "1") and r["omega_rad_s"] not in ("", "nan")]
t = np.array([float(r["time_s"]) for r in rows])
w = np.array([float(r["omega_rad_s"]) for r in rows])

stats = json.load(open(f"{JOB}/stats.json"))
aa = stats["angular_acceleration"]
alpha, w0, wf = aa["alpha_rad_s2"], aa["omega_initial"], aa["omega_final"]

# the fit window: the coast-down side, from the |omega| peak to the end of the active run
pk = int(np.argmax(np.abs(w)))
t_fit = t[pk:]

fig, ax = plt.subplots(figsize=(9.2, 4.2), dpi=200)
ax.axvspan(t_fit[0], t_fit[-1], color=C_GREY, alpha=0.07, zorder=0)
ax.axhline(0, color=C_GREY, lw=0.9, zorder=1)

ax.plot(t, np.abs(w), color=C_APP, lw=2.0, zorder=3,
        label="how fast it actually spins  $|\\omega|$")
ax.plot(t, w, color=C_MEAS, lw=2.0, zorder=3,
        label="the signed value the fit uses  $\\omega$")

# the fitted straight line on the signed value — the thing that decides the label
ax.plot(t_fit, w0 + alpha * (t_fit - t_fit[0]), color=C_ACC, lw=1.8, ls="--", zorder=4,
        label=f"constant-$\\alpha$ fit:  $\\alpha = +{alpha:.2f}$ rad/s$^2$")

i_up = int(len(t_fit) * 0.30)
ax.annotate("goes UP  $\\Rightarrow$  reported as “speeding up”",
            xy=(t_fit[i_up], w0 + alpha * (t_fit[i_up] - t_fit[0])),
            xytext=(0.30, 0.07), textcoords="axes fraction", color=C_ACC, fontsize=10.5,
            arrowprops=dict(arrowstyle="->", color=C_ACC, lw=1.4))
ax.annotate("goes DOWN  $\\Rightarrow$  the fan is slowing",
            xy=(t[int(len(t) * 0.78)], abs(w[int(len(t) * 0.78)])),
            xytext=(0.44, 0.83), textcoords="axes fraction", color=C_APP, fontsize=10.5,
            arrowprops=dict(arrowstyle="->", color=C_APP, lw=1.4))
ax.text(t_fit[0] + 0.8, 10.6, "window the slope is measured over",
        color=C_GREY, fontsize=8.5, style="italic")

ax.set_xlabel("time (s)")
ax.set_ylabel("angular velocity (rad/s)")
ax.set_title("Ceiling fan, whole clip: the same motion, read two ways", fontsize=11.5)
ax.legend(loc="lower right", fontsize=9, framealpha=0.95)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
fig.tight_layout()
fig.savefig(OUT)
print("wrote", OUT, "| alpha", alpha, "| omega", w0, "->", wf,
      "| |omega|", abs(w0), "->", abs(wf))
