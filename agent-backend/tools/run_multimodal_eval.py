#!/usr/bin/env python3
"""Multimodal-relevance evaluation: bring the FIGURE (image input) into the text
metric, then BERTScore it against the reference figures.

Motivation (advisor's "input vs output BERTScore?" ask): BERTScore is a text
metric, so a generated *figure* never enters it. Here a vision LLM captions each
figure — turning the image input into text — and we BERTScore the candidate-figure
captions against the reference-figure captions. This mirrors the whole-passage
material eval (run_material_eval.py), but on the visual channel.

  candidate figures --VLM caption--> text  \
                                              >-- BERTScore (P/R/F1) --> relevance
  reference figures --VLM caption--> text  /

Reference figures: OpenStax College Physics §6.2 (the velocity-difference geometry
figure + the car/centrifuge examples figure), the same authentic textbook section
used for the prose material eval.

Captioner: the lab's local multimodal Qwen (input: text+image), thinking OFF so the
whole budget lands in `content` (it's a reasoning model — with thinking ON, short
captions can come back empty). Captions are cached by file content hash so reruns
are cheap.

Usage:
  .venv-eval/bin/python tools/run_multimodal_eval.py \
      --ref-figs material_work/_reference/openstax_6.2/figures \
      --candidates fan=workspaces/job_a2627aa2-.../analysis/figures \
                   bike=workspaces/job_8110ab0d-.../analysis/figures ... \
      --out material_work/_eval/multimodal_eval_report.md
"""
import argparse, base64, glob, hashlib, json, pathlib, statistics, sys
import requests
from bert_score import score as bertscore

# Local multimodal Qwen (same provider as config/pi-models.json).
VLM_URL = "http://192.168.1.205:8083/v1/chat/completions"
VLM_KEY = "hwanglabyoungdumbandbreak"
VLM_MODEL = "Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf"

CAPTION_PROMPT = (
    "You are reading a physics figure about circular / centripetal motion. In 2-4 "
    "sentences, describe factually what the figure shows: the objects or quantities "
    "depicted (e.g. radius r, velocity v, centripetal acceleration a_c, angular "
    "velocity omega, the centre of rotation, the circular path) and the relationship "
    "or trend it conveys. Do not invent numbers that are not visible. Be concise."
)

# Candidate analysis figures we caption per object (skip rendered PDF page rasters
# student_edition-*.png / teacher_key-*.png — those are whole pages, not figures).
CANDIDATE_FIGS = [
    "annotated_image.png", "trajectory.png", "summary_panel.png",
    "omega_t.png", "ac_t.png", "radius_t.png", "v_t.png",
]

_NORM = {"ω": "omega", "α": "alpha", "θ": "theta", "Δ": "delta", "π": "pi",
         "²": "^2", "³": "^3", "·": "*", "×": "x", "≈": "approx", "→": "to",
         "−": "-", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-"}


def _norm(s):
    for k, v in _NORM.items():
        s = s.replace(k, v)
    return s


def _cache_path(out):
    return pathlib.Path(out).with_name("caption_cache.json")


def caption_image(path, cache):
    """VLM caption of one image, cached by file content hash."""
    raw = pathlib.Path(path).read_bytes()
    key = hashlib.sha1(raw).hexdigest()
    if key in cache:
        return cache[key]
    b64 = base64.b64encode(raw).decode()
    ext = pathlib.Path(path).suffix.lstrip(".").lower().replace("jpg", "jpeg")
    payload = {
        "model": VLM_MODEL,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": CAPTION_PROMPT},
            {"type": "image_url",
             "image_url": {"url": f"data:image/{ext};base64,{b64}"}},
        ]}],
        "max_tokens": 600, "temperature": 0.2,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    r = requests.post(VLM_URL, headers={"Authorization": f"Bearer {VLM_KEY}"},
                      json=payload, timeout=180)
    r.raise_for_status()
    msg = r.json()["choices"][0]["message"]
    txt = (msg.get("content") or "").strip()
    if not txt:
        raise RuntimeError(f"empty caption for {path} (reasoning leaked? "
                           f"reasoning_len={len(msg.get('reasoning_content') or '')})")
    cache[key] = txt
    return txt


def _t(s, n=320):
    return " ".join(_norm(s).split()[:n])


def bsprf(cands, refs):
    """Raw BERTScore (no baseline rescale) to stay comparable with the prose eval."""
    P, R, F = bertscore([_t(c) for c in cands], [_t(r) for r in refs],
                        lang="en", rescale_with_baseline=False)
    return P.tolist(), R.tolist(), F.tolist()


def msd(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return (None, None)
    m = statistics.mean(xs)
    return (m, statistics.pstdev(xs) if len(xs) > 1 else 0.0)


def find_figs(figdir):
    figdir = pathlib.Path(figdir)
    out = []
    for name in CANDIDATE_FIGS:
        p = figdir / name
        if p.exists():
            out.append((name, p))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref-figs", required=True,
                    help="dir of reference figure images (e.g. OpenStax §6.2 figures)")
    ap.add_argument("--candidates", nargs="+", required=True,
                    help="name=figdir pairs; figdir holds the per-object analysis PNGs")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    cache_p = _cache_path(args.out)
    cache = json.loads(cache_p.read_text()) if cache_p.exists() else {}

    # Reference figure captions.
    ref_imgs = sorted(glob.glob(str(pathlib.Path(args.ref_figs) / "*.jpg")) +
                      glob.glob(str(pathlib.Path(args.ref_figs) / "*.png")))
    if not ref_imgs:
        sys.exit(f"no reference figures in {args.ref_figs}")
    ref_caps = {}
    for p in ref_imgs:
        ref_caps[pathlib.Path(p).stem] = caption_image(p, cache)
        cache_p.write_text(json.dumps(cache, indent=2))
        print(f"  [ref] {pathlib.Path(p).name}")
    ref_full = " ".join(ref_caps.values())

    # Candidate figure captions, per object.
    objects = {}
    for spec in args.candidates:
        name, _, figdir = spec.partition("=")
        figs = find_figs(figdir)
        if not figs:
            print(f"  WARN: no candidate figures in {figdir} for {name}")
            continue
        caps = {}
        for fname, p in figs:
            caps[fname] = caption_image(str(p), cache)
            cache_p.write_text(json.dumps(cache, indent=2))
        objects[name] = caps
        print(f"  [cand] {name}: {len(caps)} figures captioned")

    if not objects:
        sys.exit("no candidate objects captioned")

    # HEADLINE: per object, all figure captions joined vs all reference captions
    # joined -> whole-figure-set BERTScore (parallel to the whole-passage prose number).
    names = list(objects)
    cand_full = [" ".join(objects[n].values()) for n in names]
    wp, wr, wf = bsprf(cand_full, [ref_full] * len(names))
    whole = {n: {"p": p, "r": r, "f1": f} for n, p, r, f in zip(names, wp, wr, wf)}

    # DIAGNOSTIC: best-matching reference figure for each candidate figure (which
    # reference figure each of our figures most resembles, by caption BERTScore F1).
    ref_names = list(ref_caps)
    best = {n: {} for n in names}
    for n in names:
        for fname, cap in objects[n].items():
            _, _, f1s = bsprf([cap] * len(ref_names), list(ref_caps.values()))
            bi = max(range(len(f1s)), key=lambda i: f1s[i])
            best[n][fname] = {"ref": ref_names[bi], "f1": f1s[bi]}

    # ---- report ----
    wm, ws_ = msd([whole[n]["f1"] for n in names])
    pm, ps_ = msd([whole[n]["p"] for n in names])
    rm, rs_ = msd([whole[n]["r"] for n in names])

    L = ["# Multimodal evaluation — Centri figures vs authentic textbook figures\n",
         "Brings the **figure (image input)** into the text metric: a vision LLM "
         "captions each figure, then we BERTScore the captions. Reference: OpenStax "
         "College Physics §6.2 figures (velocity-difference geometry; car/centrifuge "
         "examples). Captioner: local multimodal Qwen (thinking off). Metric: raw "
         "BERTScore (no baseline rescale), comparable to the prose material eval.\n",
         f"Reference figures: {len(ref_caps)}. Objects: {len(names)}.\n"]

    L.append("## Multimodal relevance — figure captions vs reference (mean ± SD)\n")
    L.append("| Object | BERTScore P | R | F1 |")
    L.append("|---|---|---|---|")
    for n in names:
        w = whole[n]
        L.append(f"| {n} | {w['p']:.3f} | {w['r']:.3f} | {w['f1']:.3f} |")
    L.append(f"| **mean ± SD** | {pm:.3f} ± {ps_:.3f} | {rm:.3f} ± {rs_:.3f} | "
             f"**{wm:.3f} ± {ws_:.3f}** |")

    L.append("\n## Per-figure best match to a reference figure (diagnostic, F1)\n")
    L.append("| Object | Figure | Best-match reference figure | F1 |")
    L.append("|---|---|---|---|")
    for n in names:
        for fname, b in best[n].items():
            L.append(f"| {n} | {fname} | {b['ref']} | {b['f1']:.3f} |")

    L.append("\n## Reference figure captions (VLM)\n")
    for k, v in ref_caps.items():
        L.append(f"- **{k}**: {v}")

    L.append("\n## Summary\n")
    L.append("| Metric | Value |")
    L.append("|---|---|")
    L.append(f"| Multimodal relevance (figure captions, BERTScore F1) | "
             f"**{wm:.3f} ± {ws_:.3f}** (n={len(names)}) |")
    L.append(f"| Multimodal relevance (BERTScore P) | {pm:.3f} ± {ps_:.3f} |")
    L.append(f"| Multimodal relevance (BERTScore R) | {rm:.3f} ± {rs_:.3f} |")
    L.append("\n> The figure is converted to text by an LLM caption, then scored — so "
             "the image *input* enters the same BERTScore metric used for the text "
             "*output*. This is a relevance/agreement measure on the visual channel, "
             "not a quality judgement.")

    out = pathlib.Path(args.out)
    out.write_text("\n".join(L) + "\n")
    json.dump({"whole": whole, "best_match": best, "ref_captions": ref_caps,
               "object_captions": objects,
               "summary": {"f1_mean": wm, "f1_sd": ws_, "p_mean": pm, "p_sd": ps_,
                           "r_mean": rm, "r_sd": rs_, "n": len(names)}},
              open(out.with_suffix(".json"), "w"), indent=2)
    print(f"\nMULTIMODAL relevance F1 = {wm:.3f} ± {ws_:.3f} (n={len(names)})")
    print(f"report -> {out}")


if __name__ == "__main__":
    main()
