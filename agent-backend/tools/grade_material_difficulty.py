#!/usr/bin/env python3
"""Independent difficulty signal for tiered learning material — model-free.

BERTScore measures relevance to a reference, not difficulty, and the tier labels
(basic/intermediate/advanced) are *asserted* by the generator. This tool MEASURES
two theory-grounded difficulty proxies from the prose itself so the asserted ladder
can be checked against evidence:

  1. Readability  — Flesch Reading Ease + Flesch-Kincaid Grade Level (no deps;
                    syllable heuristic). Lower ease / higher grade = harder text.
  2. Element interactivity (Cognitive Load Theory, Sweller) — the count of distinct
     physical quantities referenced + the count of explicit relations/equations
     among them. More interacting elements held simultaneously = higher intrinsic
     load = a more advanced passage.

A faithful tier ladder should show readability getting harder and element
interactivity rising basic -> intermediate -> advanced. We report the numbers and
flag any tier that breaks the monotonic order.

Usage:
  .venv-eval/bin/python tools/grade_material_difficulty.py \
      material_work/_tiers_fan/material.basic.json \
      material_work/_tiers_fan/material.intermediate.json \
      material_work/_tiers_fan/material.advanced.json \
      --out material_work/_eval/tier_difficulty_report.md
"""
import argparse, json, re, pathlib, sys

# The EI counters (QUANTITIES / RELATION_CUES / quantities_in / relations_in) live in the
# shared gate module so this tool and material_gate.cross_tier_issues score identically.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "workspace_lib"))
from analysis.material_gate import (  # noqa: E402
    QUANTITIES, RELATION_CUES, quantities_in, relations_in)


def syllables(word):
    w = re.sub(r"[^a-z]", "", word.lower())
    if not w:
        return 0
    groups = re.findall(r"[aeiouy]+", w)
    n = len(groups)
    if w.endswith("e") and not w.endswith(("le", "ie")) and n > 1:
        n -= 1
    return max(1, n)


def flesch(text):
    words = re.findall(r"[A-Za-z]+", text)
    sentences = [s for s in re.split(r"[.!?]+", text) if s.strip()]
    nw, ns = len(words), max(1, len(sentences))
    syl = sum(syllables(w) for w in words)
    if nw == 0:
        return (None, None, 0, 0)
    wps, spw = nw / ns, syl / nw
    ease = 206.835 - 1.015 * wps - 84.6 * spw
    grade = 0.39 * wps + 11.8 * spw - 15.59
    return (round(ease, 1), round(grade, 1), nw, len(sentences))


def passage(d):
    return " ".join(v for v in d.get("sections", {}).values() if isinstance(v, str))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("materials", nargs="+")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    TIER_ORDER = {"basic": 0, "intermediate": 1, "advanced": 2}
    rows = []
    for p in args.materials:
        d = json.loads(pathlib.Path(p).read_text())
        text = passage(d)
        ease, grade, nw, nsent = flesch(text)
        qs = quantities_in(text)
        rels = relations_in(text)
        rows.append({
            "file": pathlib.Path(p).name,
            "tier": d.get("tier", "?"),
            "self_label_EI": d.get("element_interactivity", "?"),
            "words": nw,
            "flesch_ease": ease,
            "fk_grade": grade,
            "n_quantities": len(qs),
            "quantities": qs,
            "n_relations": rels,
            "ei_score": len(qs) + rels,
            "concepts_introduced": len(d.get("concepts_introduced", [])),
        })

    rows.sort(key=lambda r: TIER_ORDER.get(r["tier"], 9))

    # Monotonicity checks (harder up the ladder): grade up, ease down, EI up.
    def mono(key, increasing):
        vals = [r[key] for r in rows if r[key] is not None]
        ok = all((vals[i] <= vals[i + 1]) if increasing else (vals[i] >= vals[i + 1])
                 for i in range(len(vals) - 1))
        return ok

    grade_ok = mono("fk_grade", True)
    ease_ok = mono("flesch_ease", False)
    ei_ok = mono("ei_score", True)

    L = ["# Tier difficulty — independent (model-free) signal\n",
         "Readability (Flesch) + element-interactivity count (CLT), measured from the prose.",
         "A faithful ladder gets *harder* up the tiers: FK grade ↑, reading ease ↓, EI score ↑.\n",
         "| Difficulty level | Words | Flesch ease | FK grade | Distinct quantities | Relations | **EI score** | Self-label |",
         "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        L.append(f"| {r['tier']} | {r['words']} | {r['flesch_ease']} | {r['fk_grade']} | "
                 f"{r['n_quantities']} | {r['n_relations']} | **{r['ei_score']}** | {r['self_label_EI']} |")

    L.append("\n## Monotonicity (does measured difficulty rise with the asserted tier?)\n")
    L.append(f"- FK grade increasing basic→advanced: **{'PASS' if grade_ok else 'FAIL'}**")
    L.append(f"- Reading ease decreasing basic→advanced: **{'PASS' if ease_ok else 'FAIL'}**")
    L.append(f"- Element-interactivity score increasing basic→advanced: **{'PASS' if ei_ok else 'FAIL'}**")

    L.append("\n## Quantities referenced per tier\n")
    for r in rows:
        L.append(f"- **{r['tier']}** ({r['n_quantities']}): {', '.join(r['quantities']) or '—'}")

    L.append("\n> Element interactivity = distinct physical quantities + explicit relations/"
             "equations the reader must integrate (CLT proxy). Unlike BERTScore (relevance to "
             "a reference) this measures the passage's intrinsic load directly, so the tier "
             "ladder is evidence, not an assertion.")

    out = pathlib.Path(args.out)
    out.write_text("\n".join(L) + "\n")
    json.dump({"rows": rows,
               "monotonic": {"fk_grade_up": grade_ok, "ease_down": ease_ok, "ei_up": ei_ok}},
              open(out.with_suffix(".json"), "w"), indent=2)
    for r in rows:
        print(f"{r['tier']:13s} ease={r['flesch_ease']:>5} grade={r['fk_grade']:>4} "
              f"quantities={r['n_quantities']} relations={r['n_relations']} EI={r['ei_score']}")
    print(f"monotonic: grade↑={grade_ok} ease↓={ease_ok} EI↑={ei_ok}")
    print(f"report -> {out}")


if __name__ == "__main__":
    main()
