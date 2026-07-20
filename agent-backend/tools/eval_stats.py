#!/usr/bin/env python3
"""Correlation & reliability statistics for Centri's evaluation — the layer that ties the
three evaluation axes together the way Utami (2025) §3.4.3 does:

  - Cohen's kappa + % agreement  — inter-rater reliability across human raters.
  - ICC(2,k)                     — human-vs-LLM agreement (two-way random, average measures,
                                   absolute agreement). Utami reports per-dimension ICC; ICC>0.75
                                   reads as high agreement.
  - Pearson r                    — automatic metric vs human mean (her Study-2 RQ3).

numpy-only (no scipy needed) so it runs anywhere the .venv-eval does.

Input: a tidy/long CSV with columns  item,dimension,rater,role,score
  - item      : material id (e.g. fan.basic)
  - dimension : rubric dimension (e.g. answerability) — use "overall" if you only have one score
  - rater     : rater id (teacher_a, teacher_b, llm, bertscore_f1, ...)
  - role      : one of {human, llm, auto}
  - score     : numeric (humans/llm on 1–5; auto metrics on their own scale — Pearson is
                scale-invariant so raw auto values are fine)

What it computes (per dimension, and pooled "overall"):
  - kappa/%-agreement for every pair of human raters (unweighted, on the 1–5 categories)
  - ICC(2,k) across {mean-human, llm} (and across all human raters if 2+)
  - Pearson r between mean-human and each auto/llm source

Usage:
  .venv-eval/bin/python tools/eval_stats.py --in scores.csv \
      --out material_work/_eval/eval_stats_report.md
"""
import argparse, csv, json, pathlib, itertools, statistics
from collections import defaultdict
import numpy as np


# ---- statistics -----------------------------------------------------------------

def pearson(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    if len(x) < 2 or np.std(x) == 0 or np.std(y) == 0:
        return None
    return float(np.corrcoef(x, y)[0, 1])


def cohen_kappa(a, b):
    """Unweighted Cohen's kappa + observed % agreement for two raters over aligned items."""
    a, b = list(a), list(b)
    n = len(a)
    if n == 0:
        return None, None
    po = sum(1 for i, j in zip(a, b) if i == j) / n
    cats = set(a) | set(b)
    pe = sum((a.count(c) / n) * (b.count(c) / n) for c in cats)
    kappa = (po - pe) / (1 - pe) if pe != 1 else 1.0
    return float(kappa), float(po * 100)


def icc_2k(matrix):
    """ICC(2,k): two-way random effects, average measures, absolute agreement.

    matrix: shape (n_targets, k_raters). Returns None if too small/degenerate.
    """
    X = np.asarray(matrix, float)
    if X.ndim != 2 or X.shape[0] < 2 or X.shape[1] < 2:
        return None
    n, k = X.shape
    grand = X.mean()
    row_m = X.mean(axis=1)
    col_m = X.mean(axis=0)
    ss_total = ((X - grand) ** 2).sum()
    ss_row = k * ((row_m - grand) ** 2).sum()
    ss_col = n * ((col_m - grand) ** 2).sum()
    ss_err = ss_total - ss_row - ss_col
    msr = ss_row / (n - 1)
    msc = ss_col / (k - 1)
    mse = ss_err / ((n - 1) * (k - 1))
    denom = msr + (msc - mse) / n
    if denom == 0:
        return None
    return float((msr - mse) / denom)


# ---- data wrangling -------------------------------------------------------------

def load(path):
    rows = []
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            try:
                r["score"] = float(r["score"])
            except (KeyError, ValueError):
                continue
            rows.append(r)
    return rows


def _by_dim(rows):
    dims = defaultdict(list)
    for r in rows:
        dims[r.get("dimension", "overall")].append(r)
    dims["overall"] = rows
    return dims


def _pivot(rows):
    """item -> {rater -> score}, plus rater->role."""
    table = defaultdict(dict)
    role = {}
    for r in rows:
        table[r["item"]][r["rater"]] = r["score"]
        role[r["rater"]] = r.get("role", "human")
    return table, role


def analyze_dim(rows):
    table, role = _pivot(rows)
    items = sorted(table)
    humans = sorted(r for r, ro in role.items() if ro == "human")
    llms = sorted(r for r, ro in role.items() if ro == "llm")
    autos = sorted(r for r, ro in role.items() if ro == "auto")
    out = {"n_items": len(items), "humans": humans, "llm": llms, "auto": autos,
           "kappa": [], "icc": {}, "pearson": []}

    # items where every human rated (aligned) — for kappa across humans
    aligned = [it for it in items if all(h in table[it] for h in humans)]
    for a, b in itertools.combinations(humans, 2):
        va = [table[it][a] for it in aligned]
        vb = [table[it][b] for it in aligned]
        k, pa = cohen_kappa(va, vb)
        if k is not None:
            out["kappa"].append({"pair": f"{a}~{b}", "kappa": round(k, 3),
                                 "pct_agreement": round(pa, 1), "n": len(aligned)})

    # mean-human per item
    mean_h = {it: statistics.mean([table[it][h] for h in humans if h in table[it]])
              for it in items if any(h in table[it] for h in humans)}

    # ICC(2,k) across all human raters (aligned items)
    if len(humans) >= 2 and aligned:
        m = [[table[it][h] for h in humans] for it in aligned]
        out["icc"]["humans"] = _r(icc_2k(m))
    # ICC(2,k) across {mean-human, each llm} on shared items
    for lm in llms:
        shared = [it for it in items if it in mean_h and lm in table[it]]
        if len(shared) >= 2:
            m = [[mean_h[it], table[it][lm]] for it in shared]
            out["icc"][f"human_vs_{lm}"] = _r(icc_2k(m))

    # Pearson: mean-human vs each llm/auto source
    for src in llms + autos:
        shared = [it for it in items if it in mean_h and src in table[it]]
        if len(shared) >= 2:
            x = [mean_h[it] for it in shared]
            y = [table[it][src] for it in shared]
            out["pearson"].append({"source": src, "r": _r(pearson(x, y)), "n": len(shared)})
    return out


def _r(v):
    return round(v, 3) if isinstance(v, float) else v


# ---- report ---------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True, help="tidy CSV: item,dimension,rater,role,score")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    rows = load(args.inp)
    dims = _by_dim(rows)
    result = {dim: analyze_dim(rs) for dim, rs in dims.items()}

    L = ["# Centri evaluation — correlation & reliability (Utami 2025 §3.4.3 method)\n",
         "Cohen's κ + % agreement (inter-rater), ICC(2,k) (human vs LLM), Pearson r (human vs "
         "auto/LLM). Rubric: docs/eval-rubric-ika.md.\n"]
    for dim in sorted(result, key=lambda d: (d != "overall", d)):
        a = result[dim]
        L.append(f"## {dim}  (n={a['n_items']} items; humans={len(a['humans'])}, "
                 f"llm={len(a['llm'])}, auto={len(a['auto'])})\n")
        if a["kappa"]:
            L.append("**Inter-rater (Cohen's κ):**\n\n| Rater pair | κ | % agreement | n |\n|---|---|---|---|")
            for k in a["kappa"]:
                L.append(f"| {k['pair']} | {k['kappa']} | {k['pct_agreement']} | {k['n']} |")
            L.append("")
        if a["icc"]:
            L.append("**ICC(2,k) (agreement):**\n\n| Comparison | ICC | reading |\n|---|---|---|")
            for name, v in a["icc"].items():
                tag = "—" if v is None else ("high (>0.75)" if v > 0.75 else
                                             "moderate (0.5–0.75)" if v > 0.5 else "low")
                L.append(f"| {name} | {v} | {tag} |")
            L.append("")
        if a["pearson"]:
            L.append("**Pearson r (mean-human vs source):**\n\n| Source | r | n |\n|---|---|---|")
            for p in a["pearson"]:
                L.append(f"| {p['source']} | {p['r']} | {p['n']} |")
            L.append("")
        if not (a["kappa"] or a["icc"] or a["pearson"]):
            L.append("_No human/LLM/auto pairs available yet (pending teacher ratings — next week)._\n")

    out = pathlib.Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(L) + "\n")
    json.dump(result, open(out.with_suffix(".json"), "w"), indent=2)
    print(f"report -> {out}")


if __name__ == "__main__":
    main()
