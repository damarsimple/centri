#!/usr/bin/env python3
"""Monitor Centri analysis jobs — poll /jobs every N seconds.

Usage: python3 monitor.py [poll_interval_secs=60]
"""
import requests, json, time, sys

API = "http://10.0.0.1:8088"
KEY = "changeme-random-secret-key-12345"
POLL = float(sys.argv[1]) if len(sys.argv) > 1 else 60

def fmt_sec(s):
    h, r = divmod(int(s or 0), 3600)
    m, s = divmod(r, 60)
    return f"{h}h{m:02d}m{s:02d}s" if h else f"{m}m{s:02d}s"

while True:
    r = requests.get(f"{API}/jobs", headers={"X-API-Key": KEY})
    if r.status_code != 200:
        print(f"[{time.strftime('%H:%M:%S')}] API error: {r.status_code}", flush=True)
        time.sleep(POLL)
        continue

    jobs = r.json().get("jobs", [])
    done = [j for j in jobs if j["status"] == "done"]
    failed = [j for j in jobs if j["status"] == "failed"]
    running = [j for j in jobs if j["status"] == "running"]
    queued = [j for j in jobs if j["status"] not in ("done", "failed", "running")]

    print(f"\n[{time.strftime('%H:%M:%S')}] {len(done)} done, {len(failed)} failed, "
          f"{len(running)} running, {len(queued)} queued", flush=True)

    for j in running:
        print(f"  \u25b6 {j['job_id'][:8]} {j.get('step','')} {j.get('progress_pct','?')}% "
              f"[{fmt_sec(j.get('elapsed_s'))}]", flush=True)

    if done:
        print(f"  {'ID':<10} {'omega':>7} {'ac':>7} {'cov%':>6}  time", flush=True)
        print(f"  {'-'*39}", flush=True)
        for j in done[-5:]:
            rr = requests.get(f"{API}/result/{j['job_id']}", headers={"X-API-Key": KEY})
            s = rr.json().get("stats", {}) if rr.status_code == 200 else {}
            w = f"{s.get('mean_omega', 0):>7.2f}" if s.get('mean_omega') else "     ?"
            a = f"{s.get('mean_ac', 0):>7.2f}" if s.get('mean_ac') else "     ?"
            c = f"{s.get('tracking_coverage_pct', 0):>5.1f}" if s.get('tracking_coverage_pct') else "    ?"
            print(f"  {j['job_id'][:8]}  {w}  {a}  {c:>6}  {fmt_sec(j.get('elapsed_s'))}", flush=True)

    for j in failed:
        m = requests.get(f"{API}/status/{j['job_id']}", headers={"X-API-Key": KEY})
        msg = m.json().get("message", "")[:80] if m.status_code == 200 else ""
        print(f"  \u2717 {j['job_id'][:8]} {msg}", flush=True)

    if not running and not queued:
        print("\n* All jobs finished! *", flush=True)
        break

    time.sleep(POLL)
