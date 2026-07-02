#!/usr/bin/env python3
"""Multi-reference robustness eval: score each generated learning material against a
*set* of independent English references (not just the one reorganized OpenStax §6.2),
to show the relevance number is not an artifact of a single reference choice.

For each candidate (whole 5-section passage) we BERTScore against each reference's
centripetal-focused text, then report:
  - per candidate: mean F1 over references, and best-match (max) F1 + which reference
  - overall:       mean ± SD of the per-candidate means, and of the best-matches
  - per reference: mean F1 over candidates (which references our material resembles most)

References are RAW source PDFs of varying scope (whole chapters vs tight derivations),
so each is reduced to its most centripetal-dense ~320-word window (keyword-anchored)
for a fair, comparable comparison. Reorganized OpenStax §6.2 is included as the gold
anchor. Metric: raw BERTScore F1 (no baseline rescale), comparable to the prose eval.

Usage:
  .venv-eval/bin/python tools/run_multi_reference_eval.py \
      --materials material_work/_eval/material_*.json \
      --ref-json material_work/_reference/openstax_6.2/reference.json \
      --ref-pdf-dir material_work/_reference/english \
      --out material_work/_eval/multi_reference_eval_report.md
"""
import argparse, glob, json, pathlib, re, statistics, subprocess
from bert_score import score as bertscore

SECTIONS = ["Scenario", "The variables we measured", "How the variables are related",
            "What the video shows over time", "Reading the figures"]
_NORM = {"ω": "omega", "α": "alpha", "θ": "theta", "Δ": "delta", "π": "pi",
         "²": "^2", "³": "^3", "·": "*", "×": "x", "≈": "approx", "→": "to",
         "−": "-", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-"}
KW = re.compile(r"centripetal|circular|angular|accelerat|radius|velocit|"
                r"rotat|tangent|omega|\bv\^?2\b|period", re.I)


def _norm(s):
    for k, v in _NORM.items():
        s = s.replace(k, v)
    return s


def load_material(path):
    d = json.loads(pathlib.Path(path).read_text())
    secs = d.get("sections", d)
    return " ".join(_norm(secs.get(s, "")) for s in SECTIONS if isinstance(secs.get(s), str))


def keyword_window(text, n=320):
    """Most centripetal-dense n-word window of a long document (keyword-anchored)."""
    words = _norm(text).split()
    if len(words) <= n:
        return " ".join(words)
    # prefix sum of keyword hits per word
    hits = [1 if KW.search(w) else 0 for w in words]
    pref = [0]
    for h in hits:
        pref.append(pref[-1] + h)
    best_i, best_score = 0, -1
    for i in range(0, len(words) - n + 1, 20):  # stride 20 for speed
        sc = pref[i + n] - pref[i]
        if sc > best_score:
            best_score, best_i = sc, i
    return " ".join(words[best_i:best_i + n])


def pdf_text(path):
    try:
        out = subprocess.run(["pdftotext", "-q", str(path), "-"],
                             capture_output=True, text=True, timeout=60).stdout
    except Exception:
        return ""
    return out


def _t(s, n=320):
    return " ".join(s.split()[:n])


def bsf1(cands, refs):
    _, _, F = bertscore([_t(c) for c in cands], [_t(r) for r in refs],
                        lang="en", rescale_with_baseline=False)
    return F.tolist()


def msd(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return (None, None)
    return (statistics.mean(xs), statistics.pstdev(xs) if len(xs) > 1 else 0.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--materials", nargs="+", required=True)
    ap.add_argument("--ref-json", required=True, help="reorganized gold reference (OpenStax §6.2)")
    ap.add_argument("--ref-pdf-dir", required=True, help="dir of raw reference PDFs")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    mat_paths = []
    for m in args.materials:
        mat_paths += sorted(glob.glob(m)) if any(c in m for c in "*?[") else [m]
    mat_paths = [p for p in mat_paths if "report" not in pathlib.Path(p).stem]
    mats = [(pathlib.Path(p).stem.replace("material_", ""), load_material(p)) for p in mat_paths]

    # references: gold (reorganized §6.2) + each raw PDF reduced to its centripetal window
    refs = {}
    gold = json.loads(pathlib.Path(args.ref_json).read_text())
    gsec = gold.get("sections", gold)
    refs["openstax_6.2 (reorganized gold)"] = _norm(" ".join(
        v for v in gsec.values() if isinstance(v, str)))
    for pdf in sorted(glob.glob(str(pathlib.Path(args.ref_pdf_dir) / "*.pdf"))):
        name = pathlib.Path(pdf).stem
        txt = pdf_text(pdf)
        if not txt.strip():
            print(f"  WARN: empty text from {name}")
            continue
        refs[name] = keyword_window(txt)
    print(f"candidates={len(mats)}  references={len(refs)}")

    ref_names = list(refs)
    # F1[candidate][reference]
    F1 = {name: {} for name, _ in mats}
    for cname, ctext in mats:
        scores = bsf1([ctext] * len(ref_names), [refs[r] for r in ref_names])
        for r, s in zip(ref_names, scores):
            F1[cname][r] = s

    # aggregates
    per_cand_mean = {c: msd(list(F1[c].values()))[0] for c, _ in mats}
    per_cand_best = {}
    for c, _ in mats:
        r = max(F1[c], key=lambda k: F1[c][k])
        per_cand_best[c] = (r, F1[c][r])
    per_ref_mean = {r: msd([F1[c][r] for c, _ in mats])[0] for r in ref_names}

    gold_key = "openstax_6.2 (reorganized gold)"
    gold_mean = msd([F1[c][gold_key] for c, _ in mats])

    mm, ms = msd(list(per_cand_mean.values()))
    bm, bs = msd([v for _, v in per_cand_best.values()])

    L = ["# Multi-reference robustness — learning material vs a SET of English references\n",
         "Each generated material (whole 5-section passage) is BERTScored against every "
         "reference, to show the relevance number is not an artifact of one reference. "
         "Raw PDFs (varying scope) are reduced to their most centripetal-dense ~320-word "
         "window; reorganized OpenStax §6.2 is the gold anchor. Metric: raw BERTScore F1.\n",
         f"Candidates: {len(mats)}. References: {len(refs)} "
         f"(1 reorganized gold + {len(refs)-1} raw English PDFs).\n"]

    L.append("## Headline\n")
    L.append("| Measure | Value |")
    L.append("|---|---|")
    L.append(f"| Relevance vs reorganized OpenStax §6.2 (gold anchor) | "
             f"**{gold_mean[0]:.3f} ± {gold_mean[1]:.3f}** (n={len(mats)}) |")
    L.append(f"| Mean relevance across the whole reference set | "
             f"**{mm:.3f} ± {ms:.3f}** (n={len(mats)} candidates × {len(refs)} refs) |")
    L.append(f"| Best-matching reference per candidate (max F1) | "
             f"**{bm:.3f} ± {bs:.3f}** (n={len(mats)}) |")

    L.append("\n## Per-candidate (mean over references, and best match)\n")
    L.append("| Object | mean F1 over refs | best F1 | best-match reference |")
    L.append("|---|---|---|---|")
    for c, _ in mats:
        r, v = per_cand_best[c]
        L.append(f"| {c} | {per_cand_mean[c]:.3f} | {v:.3f} | {r} |")

    L.append("\n## Per-reference (mean F1 over candidates) — which references our material resembles\n")
    L.append("| Reference | mean F1 over candidates |")
    L.append("|---|---|")
    for r in sorted(ref_names, key=lambda k: -per_ref_mean[k]):
        L.append(f"| {r} | {per_ref_mean[r]:.3f} |")

    L.append("\n> **Reading it:** the gold-anchor number is the official metric; the "
             "set-wide mean shows where our material sits against an *independent* English "
             "reference set, and the best-match shows the closest single source. Raw PDFs "
             "vary in scope (whole chapters vs tight derivations), so set-wide numbers are a "
             "robustness band, not a single curated comparison. Same caveat as the prose "
             "eval: same-domain physics text shares vocabulary, so BERTScore floors high.")

    out = pathlib.Path(args.out)
    out.write_text("\n".join(L) + "\n")
    json.dump({"F1": F1, "per_cand_mean": per_cand_mean,
               "per_cand_best": {c: {"ref": r, "f1": v} for c, (r, v) in per_cand_best.items()},
               "per_ref_mean": per_ref_mean,
               "headline": {"gold_mean": gold_mean[0], "gold_sd": gold_mean[1],
                            "set_mean": mm, "set_sd": ms, "best_mean": bm, "best_sd": bs,
                            "n_candidates": len(mats), "n_refs": len(refs)}},
              open(out.with_suffix(".json"), "w"), indent=2)
    print(f"\ngold §6.2 F1   = {gold_mean[0]:.3f} ± {gold_mean[1]:.3f}")
    print(f"set-wide mean  = {mm:.3f} ± {ms:.3f}  (over {len(refs)} refs)")
    print(f"best-match     = {bm:.3f} ± {bs:.3f}")
    print(f"report -> {out}")


if __name__ == "__main__":
    main()
