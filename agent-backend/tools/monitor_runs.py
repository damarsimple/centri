#!/usr/bin/env python3
"""Poll the 9 validation jobs to completion and emit a cross-run comparison.

Reads /tmp/run_jobs.tsv (video\trun\ttemplate\tjob_id), polls /status until every
job is terminal, fetches /result for each, then reports per-video cross-run spread
of period_s / mean_omega / stable_mean_omega (the "same video -> same data" test)
plus accuracy vs the phone-gyro ground truth.
"""
import csv, json, math, statistics as st, time, urllib.request
from pathlib import Path

API = "http://10.0.0.1:8088"
KEY = "changeme-random-secret-key-12345"
LOG = Path("/tmp/run_monitor.log")
GT = {  # gyro_gamma-derived ground truth (rad/s, s), see gt_harness
    "IMG_3071": (7.357, 0.854), "IMG_3072": (4.806, 1.307), "IMG_3075": (5.811, 1.081),
}


def get(path):
    req = urllib.request.Request(API + path, headers={"X-API-Key": KEY})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)


def jobs():
    rows = []
    for line in Path("/tmp/run_jobs.tsv").read_text().splitlines():
        v, run, tmpl, jid = line.split("\t")
        rows.append({"video": v, "run": run, "job_id": jid})
    return rows


def flat(stats, *path, default=None):
    d = stats
    for k in path:
        if not isinstance(d, dict) or k not in d:
            return default
        d = d[k]
    return d


def log(msg):
    LOG.write_text((LOG.read_text() if LOG.exists() else "") + msg + "\n")
    print(msg, flush=True)


def main():
    rows = jobs()
    done = {}
    deadline = time.time() + 3 * 3600
    while time.time() < deadline:
        states = {}
        for r in rows:
            jid = r["job_id"]
            if jid in done:
                states[jid] = "done" if done[jid] else "failed"
                continue
            try:
                s = get(f"/status/{jid}")
            except Exception as e:
                states[jid] = f"err:{e}"
                continue
            stt = s.get("status")
            states[jid] = f"{stt}/{s.get('progress_pct','?')}%"
            if stt in ("done", "completed"):
                try:
                    res = get(f"/result/{jid}")
                    done[jid] = res.get("stats")
                except Exception:
                    done[jid] = None
            elif stt in ("failed", "error"):
                done[jid] = None
        snap = " | ".join(f"{r['video'][-4:]}{r['run'][-1]}:{states[r['job_id']]}" for r in rows)
        log(f"[{time.strftime('%H:%M:%S')}] {snap}")
        if len(done) == len(rows):
            break
        time.sleep(60)

    # ── Report ──────────────────────────────────────────────────────────────
    log("\n================= CROSS-RUN COMPARISON (new flow, 0.4m calib) =================")
    byvid = {}
    for r in rows:
        s = done.get(r["job_id"])
        if not s:
            log(f"  {r['video']} {r['run']}: FAILED / no stats")
            continue
        period = flat(s, "period_and_frequency", "period_s")
        mo = flat(s, "summary", "mean_omega")
        smo = flat(s, "stable_phase", "stable_mean_omega")
        ppm = flat(s, "calibration", "px_per_m")
        drift = flat(s, "calibration", "center_drift_px")
        sv = s.get("schema_version")
        byvid.setdefault(r["video"], []).append((r["run"], period, mo, smo, ppm, drift))
        log(f"  {r['video']} {r['run']}: schema_v={sv} period={period} mean_omega={mo} "
            f"stable_omega={smo} px_per_m={ppm} drift={drift}")

    log("\n--- per-video spread (same video should now AGREE) ---")
    for v, runs in sorted(byvid.items()):
        ps = [x[1] for x in runs if isinstance(x[1], (int, float))]
        ms = [x[2] for x in runs if isinstance(x[2], (int, float))]
        gt = GT.get(v)
        if ps:
            spread = (max(ps) - min(ps)) / min(ps) * 100 if min(ps) else 0
            line = f"  {v}: {len(ps)} runs  period {min(ps):.3f}-{max(ps):.3f}s ({spread:.1f}% spread)"
            if gt:
                line += f"  | gyro period {gt[1]:.3f}s, mean_omega {gt[0]:.3f}"
            log(line)
            if ms:
                mspread = (max(ms) - min(ms)) / abs(min(ms)) * 100 if min(ms) else 0
                log(f"      mean_omega {min(ms):.3f}-{max(ms):.3f} ({mspread:.1f}% spread)")
    log("\nDONE.")


if __name__ == "__main__":
    main()
