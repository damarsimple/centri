#!/usr/bin/env python3
"""Classify the English reference corpus into basic / intermediate / advanced-appropriate
parts, so BERTScore can be re-run PER DIFFICULTY (note-1: "divide the 19-reference set by
difficulty into three parts, then re-run the eval"). A tier compared only against
tier-matched references is the honest test the flat n=5 F1 could not give (deck p.7).

Heuristic, model-free — reuses the element-interactivity counters from material_gate.py so a
reference is scored on the SAME axis the generated material is:
  - basic         : conceptual, no equations (0 relations, few quantities)
  - intermediate  : core-formula application (some relations, several quantities)
  - advanced      : α / time-evolution / proportionality present (alpha or many relations)

Emits a manifest JSON (reference path -> assigned difficulty + EI features) and, with
--copy, symlinks/copies each reference into basic/ intermediate/ advanced/ subdirs ready for
run_multi_reference_eval.py. The 19-source set lives in material_work/ (not this clone), so
the actual run is a runbook step; this tool is the classifier it invokes.

Usage:
  python tools/split_references_by_difficulty.py \
      --refs 'material_work/_reference/english/*.json' \
      --out  material_work/_reference/by_difficulty/manifest.json [--copy]
"""
import argparse, json, glob, pathlib, shutil, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "workspace_lib"))
from analysis.material_gate import quantities_in, relations_in  # noqa: E402

ALPHA_CUES = ("angular acceleration", "alpha", "dω/dt", "d(omega)/dt", "spin up",
              "spin-up", "coast", "time evolution", "proportional to", "limit")


def _text(d):
    secs = d.get("sections", d)
    if isinstance(secs, dict):
        return " ".join(v for v in secs.values() if isinstance(v, str))
    return d.get("text", "") if isinstance(d, dict) else str(d)


def classify(text):
    t = text.lower()
    nq = len(quantities_in(text))
    nr = relations_in(text)
    has_alpha = any(c in t for c in ALPHA_CUES)
    if has_alpha or nr >= 8:
        level = "advanced"
    elif nr >= 2 and nq >= 3:
        level = "intermediate"
    else:
        level = "basic"
    return level, {"quantities": nq, "relations": nr, "alpha_cues": has_alpha}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refs", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--copy", action="store_true",
                    help="also copy each reference into <out_dir>/<level>/")
    args = ap.parse_args()

    paths = []
    for r in args.refs:
        paths += sorted(glob.glob(r)) if any(c in r for c in "*?[") else [r]

    manifest, buckets = [], {"basic": [], "intermediate": [], "advanced": []}
    for p in paths:
        try:
            d = json.loads(pathlib.Path(p).read_text())
        except Exception as e:  # noqa: BLE001
            print(f"!! skip {p}: {e}")
            continue
        level, feats = classify(_text(d))
        manifest.append({"path": p, "level": level, **feats})
        buckets[level].append(p)
        print(f"{level:13s} {pathlib.Path(p).name}  (q={feats['quantities']}, "
              f"r={feats['relations']}, alpha={feats['alpha_cues']})")

    out = pathlib.Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"manifest": manifest,
                               "counts": {k: len(v) for k, v in buckets.items()}}, indent=2))
    print(f"\ncounts: " + ", ".join(f"{k}={len(v)}" for k, v in buckets.items()))
    print(f"manifest -> {out}")

    if args.copy:
        base = out.parent
        for level, ps in buckets.items():
            d = base / level; d.mkdir(parents=True, exist_ok=True)
            for p in ps:
                shutil.copy(p, d / pathlib.Path(p).name)
        print(f"copied references into {base}/(basic|intermediate|advanced)/")


if __name__ == "__main__":
    main()
