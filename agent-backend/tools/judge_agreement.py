#!/usr/bin/env python3
"""Agreement between two LLM judges scored on the frozen prompts — fills P-MAGIC's kappa column.

Until there were two raters, the Cohen's kappa column of the judge table could only be a dash: a
reliability figure needs someone to disagree with. Two models scoring the identical frozen prompt
give a real number per sub-dimension, in the same shape P-MAGIC reports it.

What it is NOT: this is model-vs-model agreement. P-MAGIC's kappa = 0.76 is between HUMAN raters,
and two LLMs agreeing tells you the rubric is legible, not that it is valid. The teacher panel
still has to fill the human column.

Kappa on a 1-5 rating scale is reported QUADRATIC-WEIGHTED by default (scoring 4 against 5 is a
near-miss; 1 against 5 is not), with the unweighted value alongside. Where a criterion is scored
with zero variance by BOTH raters, every weight-versus-expectation ratio is 0/0 and kappa is
undefined — reported as 'n/d', never as 0.0, because "they always agreed" and "they never agreed"
must not print the same.

Usage:
  python tools/judge_agreement.py --a material_work/_eval/judge_2026-07-29 --a-label Qwen3.6-35B \
      --b material_work/_eval/judge_claude_2026-07-31 --b-label 'Claude Opus 5' \
      --out material_work/_eval/judge_agreement_2026-07-31.md
"""
import argparse
import json
import pathlib
import statistics
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from run_llm_judge import AXES, CRITERIA  # noqa: E402 — one rubric

TIERS = ["basic", "intermediate", "advanced"]
CATEGORIES = [1, 2, 3, 4, 5]
UNDEFINED = "n/d"


def read_dir(judge_dir):
    """{(clip, tier): {criterion: score}} from judge_<clip>.md files."""
    out = {}
    for p in sorted(pathlib.Path(judge_dir).glob("judge_*.md")):
        clip = p.stem.replace("judge_", "")
        for line in p.read_text().splitlines():
            if not line.startswith("| material."):
                continue
            c = [x.strip() for x in line.strip().strip("|").split("|")]
            tier = c[1]
            if tier not in TIERS:
                continue
            scores = {}
            for name, cell in zip(CRITERIA, c[2:2 + len(CRITERIA)]):
                try:
                    scores[name] = int(cell)
                except ValueError:
                    scores[name] = None
            out[(clip, tier)] = scores
    return out


def kappa(pairs, weighting="quadratic"):
    """Cohen's kappa over (a, b) rating pairs; None when the statistic is undefined."""
    pairs = [(a, b) for a, b in pairs if a in CATEGORIES and b in CATEGORIES]
    n = len(pairs)
    if n == 0:
        return None
    k = len(CATEGORIES)
    idx = {c: i for i, c in enumerate(CATEGORIES)}

    def w(i, j):
        if weighting == "quadratic":
            return ((i - j) / (k - 1)) ** 2
        if weighting == "linear":
            return abs(i - j) / (k - 1)
        return 0.0 if i == j else 1.0

    obs = [[0] * k for _ in range(k)]
    for a, b in pairs:
        obs[idx[a]][idx[b]] += 1
    rows = [sum(r) for r in obs]
    cols = [sum(obs[i][j] for i in range(k)) for j in range(k)]

    # Both are a weighted disagreement PER PAIR: observed, and what chance alone would give from
    # the two raters' marginals. (den keeps a single 1/n^2 — the marginals carry one n each.)
    num = sum(w(i, j) * obs[i][j] for i in range(k) for j in range(k)) / n
    den = sum(w(i, j) * rows[i] * cols[j] for i in range(k) for j in range(k)) / (n * n)
    if den == 0:
        # No disagreement was POSSIBLE under chance — every pair fell in one cell.
        return None
    return 1.0 - num / den


def pearson(xs, ys):
    if len(xs) < 2:
        return None
    mx, my = statistics.mean(xs), statistics.mean(ys)
    sx = sum((x - mx) ** 2 for x in xs) ** 0.5
    sy = sum((y - my) ** 2 for y in ys) ** 0.5
    if sx == 0 or sy == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy)


def fmt(v, nd=2):
    return UNDEFINED if v is None else f"{v:.{nd}f}"


def criterion_stats(a, b, crit, keys):
    pairs = [(a[k].get(crit), b[k].get(crit)) for k in keys
             if a[k].get(crit) is not None and b[k].get(crit) is not None]
    if not pairs:
        return None
    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]
    exact = sum(1 for x, y in pairs if x == y) / len(pairs)
    within1 = sum(1 for x, y in pairs if abs(x - y) <= 1) / len(pairs)
    return {
        "n": len(pairs),
        "mean_a": statistics.mean(xs), "mean_b": statistics.mean(ys),
        "delta": statistics.mean(ys) - statistics.mean(xs),
        "exact": exact, "within1": within1,
        "kappa_q": kappa(pairs, "quadratic"),
        "kappa_u": kappa(pairs, "unweighted"),
        "r": pearson(xs, ys),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True)
    ap.add_argument("--b", required=True)
    ap.add_argument("--a-label", default="judge A")
    ap.add_argument("--b-label", default="judge B")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    A, B = read_dir(args.a), read_dir(args.b)
    keys = sorted(set(A) & set(B))
    if not keys:
        sys.exit("no worksheets in common")
    only_a, only_b = sorted(set(A) - set(B)), sorted(set(B) - set(A))

    L = [f"# Judge agreement — {args.a_label} vs {args.b_label}\n",
         f"Paired on {len(keys)} worksheets x {len(CRITERIA)} criteria "
         f"= {len(keys) * len(CRITERIA)} rating pairs. Both raters scored the byte-identical "
         "frozen prompt (`tools/export_judge_prompts.py`).\n",
         "**This is model-vs-model agreement.** It measures whether the rubric is legible to two "
         "different readers, not whether its scores are valid. The human column is still empty.\n"]
    if only_a or only_b:
        L.append(f"Unpaired: {len(only_a)} only in A, {len(only_b)} only in B.\n")

    # per criterion
    L += ["## Per criterion\n",
          f"| Criterion | n | {args.a_label} M | {args.b_label} M | Δ | exact | ±1 | "
          "κ (quad) | κ (unw) | r |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    all_pairs = []
    for axis, crits in AXES.items():
        for crit in crits:
            s = criterion_stats(A, B, crit, keys)
            if not s:
                continue
            all_pairs += [(A[k].get(crit), B[k].get(crit)) for k in keys]
            L.append(f"| {crit} | {s['n']} | {s['mean_a']:.2f} | {s['mean_b']:.2f} | "
                     f"{s['delta']:+.2f} | {s['exact']:.0%} | {s['within1']:.0%} | "
                     f"{fmt(s['kappa_q'])} | {fmt(s['kappa_u'])} | {fmt(s['r'])} |")

    # overall + per tier
    def block(title, subset):
        pairs = [(A[k].get(c), B[k].get(c)) for k in subset for c in CRITERIA
                 if A[k].get(c) is not None and B[k].get(c) is not None]
        xs = [p[0] for p in pairs]
        ys = [p[1] for p in pairs]
        exact = sum(1 for x, y in pairs if x == y) / len(pairs)
        within1 = sum(1 for x, y in pairs if abs(x - y) <= 1) / len(pairs)
        return (f"| {title} | {len(pairs)} | {statistics.mean(xs):.2f} | "
                f"{statistics.mean(ys):.2f} | {statistics.mean(ys) - statistics.mean(xs):+.2f} | "
                f"{exact:.0%} | {within1:.0%} | {fmt(kappa(pairs, 'quadratic'))} | "
                f"{fmt(kappa(pairs, 'unweighted'))} | {fmt(pearson(xs, ys))} |")

    L += ["\n## Overall and per level\n",
          f"| Set | n pairs | {args.a_label} M | {args.b_label} M | Δ | exact | ±1 | "
          "κ (quad) | κ (unw) | r |",
          "|---|---|---|---|---|---|---|---|---|---|",
          block("All 12 criteria", keys)]
    for tier in TIERS:
        sub = [k for k in keys if k[1] == tier]
        if sub:
            L.append(block(tier, sub))

    # where they disagree most, worksheet by worksheet
    L += ["\n## Largest disagreements\n", "| Worksheet | Criterion | "
          f"{args.a_label} | {args.b_label} | Δ |", "|---|---|---|---|---|"]
    gaps = []
    for k in keys:
        for c in CRITERIA:
            x, y = A[k].get(c), B[k].get(c)
            if x is not None and y is not None and abs(x - y) >= 2:
                gaps.append((abs(x - y), k, c, x, y))
    for _, k, c, x, y in sorted(gaps, reverse=True)[:20]:
        L.append(f"| {k[0]} {k[1]} | {c} | {x} | {y} | {y - x:+d} |")
    if not gaps:
        L.append("| — | no gap of 2 or more | | | |")

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(L) + "\n")

    summary = {"a": args.a_label, "b": args.b_label, "n_worksheets": len(keys),
               "kappa_quadratic": kappa(all_pairs, "quadratic"),
               "kappa_unweighted": kappa(all_pairs, "unweighted"),
               "per_criterion": {c: criterion_stats(A, B, c, keys) for c in CRITERIA}}
    out.with_suffix(".json").write_text(json.dumps(summary, indent=2))
    print("\n".join(L[-0:]) if False else f"report -> {out}")
    print(f"overall kappa (quadratic) = {fmt(summary['kappa_quadratic'])}, "
          f"unweighted = {fmt(summary['kappa_unweighted'])}")


if __name__ == "__main__":
    main()
