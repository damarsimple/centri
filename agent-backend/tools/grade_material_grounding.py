#!/usr/bin/env python3
"""Deterministic grounding / consistency verifier for generated learning material.

Thin CLI/markdown wrapper over ``workspace_lib/analysis/material_gate.py`` — the SAME
module the live pipeline gate runs, so the repo verifier and the in-workspace gate can
no longer drift. Checks the material against the measured GROUND TRUTH (the seed) and
against itself, objectively, no model:

  1. ARITHMETIC CLOSURE — every explicit numeric claim must actually compute.
  2. NUMBER GROUNDING   — every physics-like number must trace to a seed value.
  3. TIER COMPLIANCE    — basic: no equations/symbols; intermediate: structured
     a_c = omega^2 * r; advanced: alpha + a timeline instant.
  4. MOTION FAITHFULNESS — accelerating/decelerating clips are never called steady.
  5. VOCABULARY         — no tracking/pipeline words, no dynamics words (kinematics only).
  6. CROSS-TIER         — titles equal, worked instants distinct, EI rises up the ladder.

Usage:
  python tools/grade_material_grounding.py \
      --seed material_work/<obj>/material_seed.json \
      --materials material.basic.json material.intermediate.json material.advanced.json \
      --out material_work/_eval/grounding_report.md
A single material may carry its own tier via the "tier" field; --seed is optional but
arithmetic/tier/motion/vocab checks run without it.
"""
import argparse, json, glob, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "workspace_lib"))
from analysis import material_gate as G  # noqa: E402

# The tier → timeline-index anchors the generator assigns (kept in sync with
# material_tiers.TIER_ANCHORS); used only for the cross-tier worked-instant check.
TIER_ANCHORS = {"intermediate": [1], "advanced": [2, 0, 3]}


def _unreliable(seed):
    return bool(seed) and not (seed.get("measurement_quality") or {}).get("reliable", True)


def grade_one(mat, seed):
    secs = mat.get("sections", mat)
    text = "\n".join(v for v in secs.values() if isinstance(v, str))
    tier = mat.get("tier", "?")
    unreliable = _unreliable(seed)
    ar = G.arithmetic_claims(text)
    ar_fail = [c for c in ar if not c["ok"]]
    ung = G.ungrounded_numbers(text, G.allowed_values(seed)) if seed else []
    tc = (G.tier_compliance(tier, text, unreliable=unreliable)
          if tier in ("basic", "intermediate", "advanced") else [])
    mf = G.motion_faithfulness(seed, text) if seed else []
    vc = G.vocab_issues(text)
    return {"tier": tier, "arith": ar, "arith_fail": ar_fail, "ungrounded": ung,
            "tier_issues": tc, "motion_issues": mf, "vocab_issues": vc,
            "ok": not (ar_fail or ung or tc or mf or vc)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", default=None)
    ap.add_argument("--materials", nargs="+", required=True)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    paths = []
    for m in args.materials:
        paths += sorted(glob.glob(m)) if any(c in m for c in "*?[") else [m]
    seed = json.loads(pathlib.Path(args.seed).read_text()) if args.seed else None

    L = ["# Material grounding & consistency report",
         "Deterministic checks against the measured seed (no model). "
         "PASS = every numeric claim computes, every number traces to the seed, tier rules "
         "hold, motion described faithfully, no tracking/dynamics vocabulary.\n"]
    n_ok = 0
    mats = {}
    for p in paths:
        mat = json.loads(pathlib.Path(p).read_text())
        if mat.get("tier") in ("basic", "intermediate", "advanced"):
            mats[mat["tier"]] = mat
        r = grade_one(mat, seed)
        n_ok += r["ok"]
        name = pathlib.Path(p).stem
        L.append(f"## {name}  —  tier={r['tier']}  —  {'✅ PASS' if r['ok'] else '❌ FAIL'}")
        L.append(f"- arithmetic claims: {len(r['arith'])} found, "
                 f"**{len(r['arith_fail'])} fail**")
        for c in r["arith_fail"]:
            L.append(f"    - ❌ `{c['claim']}` → computes to **{c['computed']}**, stated **{c['stated']}**")
        if r["arith"] and not r["arith_fail"]:
            L.append(f"    - ✅ all {len(r['arith'])} compute "
                     + ", ".join(f"`{c['claim']}`={c['computed']}" for c in r["arith"][:3])
                     + (" …" if len(r["arith"]) > 3 else ""))
        if seed:
            L.append(f"- ungrounded numbers: **{len(r['ungrounded'])}**")
            for u in r["ungrounded"]:
                L.append(f"    - ❌ {u['value']}  in  {u['context']}")
        L.append(f"- tier compliance: {'✅ ok' if not r['tier_issues'] else '❌ ' + '; '.join(r['tier_issues'])}")
        if seed:
            L.append(f"- motion faithfulness: {'✅ ok' if not r['motion_issues'] else '❌ ' + '; '.join(r['motion_issues'])}")
        if r["vocab_issues"]:
            L.append(f"- vocabulary: ❌ {len(r['vocab_issues'])} hit(s)")
            for v in r["vocab_issues"]:
                L.append(f"    - ❌ [{v['kind']}] '{v['word']}'  in  {v['context']}")
        else:
            L.append("- vocabulary: ✅ ok")
        L.append("")

    # Cross-tier section (only when all three tiers are present).
    if seed and len(mats) >= 2:
        ct = G.cross_tier_issues(mats, seed, TIER_ANCHORS, unreliable=_unreliable(seed))
        L.append("## Cross-tier consistency")
        if ct:
            for c in ct:
                L.append(f"- ❌ {c}")
        else:
            L.append("- ✅ titles equal, worked instants distinct, element interactivity rises")
        L.append("")

    L.insert(2, f"**{n_ok}/{len(paths)} materials fully grounded.**\n")
    report = "\n".join(L)
    print(report)
    if args.out:
        out = pathlib.Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report + "\n")
        print(f"\nreport -> {out}")


if __name__ == "__main__":
    main()
