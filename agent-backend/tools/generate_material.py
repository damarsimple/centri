#!/usr/bin/env python3
"""Module D (quick path): turn a material_seed.json into authentic grounded
learning material via the lab Qwen, then save material.md + material.json.

The seed is the ONLY source of numbers; Qwen supplies fluent prose. Output is
lightly structured under fixed section headers so it stays comparable across
objects and against a hand-built reference (for BERTScore).

Usage:  python tools/generate_material.py material_work/<obj-dir> [...]
        (each dir must contain material_seed.json)
"""
import json, sys, os, re, pathlib, urllib.request

BASE = os.environ.get("PI_INFERENCE_URL", "http://192.168.1.205:8083") + "/v1/chat/completions"
KEY = os.environ.get("PI_INFERENCE_API_KEY", "hwanglabyoungdumbandbreak")
MODEL = "Qwen3.6-35B"

SECTIONS = [
    "Scenario",
    "The variables we measured",
    "How the variables are related",
    "What the video shows over time",
    "Reading the figures",
]

SYSTEM = (
    "You are a physics teacher writing a short, multimodal learning passage about "
    "circular motion for intro-physics students. You are given GROUND-TRUTH "
    "measurements extracted from a real video of an object moving in a circle. "
    "Write authentic, flowing explanatory prose that TEACHES the concepts by "
    "grounding them in this specific observed motion.\n"
    "Hard rules:\n"
    "1. Use ONLY the numbers in the data. Never invent, extrapolate, or introduce "
    "quantities that are not given. Quote values with their units.\n"
    "2. Define each variable in plain language, then tie it to the measured value.\n"
    "3. State the formula relationships and show they hold for THIS object. When you "
    "demonstrate an identity numerically (e.g. a_c = omega^2 * r or T = 2*pi/omega), "
    "use ONE single timeline instant, NOT the time-averaged summary means: for "
    "non-uniform motion the means do not satisfy these identities (Jensen). Every "
    "arithmetic claim you write must actually compute.\n"
    "4. Use the time-anchored timeline to narrate how the motion evolves across the "
    "clip (e.g. 'at t = 3 s it is turning at ... by t = 7 s it has sped up to ...'). "
    "If the motion type is accelerating/decelerating, explain angular acceleration "
    "from those same numbers.\n"
    "5. Refer naturally to the annotated figures (image, graph, table).\n"
    "6. This is teaching material ONLY — do NOT write any questions, quizzes, "
    "exercises, or 'try this' prompts.\n"
    "7. ~350-550 words total. Use EXACTLY these markdown section headers, in order, "
    "nothing before the first header:\n"
    + "\n".join(f"## {h}" for h in SECTIONS)
)


def _facts(seed):
    """Compact, model-friendly rendering of the seed."""
    lines = [f"object: {seed.get('scene_title') or seed.get('object_name')}",
             f"rotation_direction: {seed.get('rotation_direction')}",
             f"clip_duration_s: {seed.get('active_duration_s')}"]
    lines.append("measured variables:")
    for v in seed["variables"]:
        val = v["value"]
        val = round(val, 3) if isinstance(val, (int, float)) else val
        lines.append(f"  - {v['name']} ({v['symbol']}) = {val} {v['unit']}  "
                     f"[{v['definition']}]")
    lines.append("formula relations (ground truth):")
    for r in seed["relations"]:
        lines.append(f"  - {r['formula']}   ({r['plain']})")
    aa = seed.get("angular_acceleration")
    if aa:
        lines.append(f"motion type: {aa['motion_type']} — {aa.get('plain','')}")
        lines.append(f"  alpha = {round(aa['alpha_rad_s2'],3)} rad/s^2 "
                     f"(fit R^2={round(aa['alpha_r2'],5)}), "
                     f"omega {round(aa['omega_initial'],2)} -> {round(aa['omega_final'],2)} rad/s, "
                     f"mean tangential accel a_t = {round(aa['a_t_mean_m_s2'],2)} m/s^2")
        lines.append(f"  relation: {aa['relation']}")
    else:
        lines.append("motion type: approximately uniform (no angular-acceleration block)")
    if seed.get("timeline"):
        lines.append("time-anchored samples (pipeline's own per-frame values):")
        for s in seed["timeline"]:
            lines.append(f"  - t={s['t_s']} s: omega={s['omega_rad_s']} rad/s, "
                         f"v={s['v_m_s']} m/s, a_c={s['a_c_m_s2']} m/s^2")
    con = seed.get("consistency_note", {})
    if con:
        lines.append("consistency rule: " + con.get("means_are_time_averages", ""))
    cn = seed.get("calibration_note", {})
    if cn:
        lines.append(f"calibration note: scale from a reference of "
                     f"{cn.get('reference_physical_size_m')} m "
                     f"({cn.get('reference_source')}); {cn.get('caveat')}")
    figs = seed.get("figures", {})
    if figs:
        lines.append("available figures: " + ", ".join(figs.keys()))
    return "\n".join(lines)


def _call_qwen(system, user, temperature=0.4, max_tokens=24000, think=True):
    # Qwen3 is a reasoning model. With thinking ON it reasons in `reasoning_content`
    # (we ignore that) and writes the final prose in `content` — but it needs enough
    # budget to finish thinking AND answer, or content comes back empty. The model
    # handles ~180k ctx, so a generous max_tokens is fine.
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "chat_template_kwargs": {"enable_thinking": think},
    }).encode()
    req = urllib.request.Request(BASE, data=body, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {KEY}",
    })
    with urllib.request.urlopen(req, timeout=600) as resp:
        out = json.loads(resp.read())
    ch = out["choices"][0]
    content = ch["message"].get("content") or ""
    if ch.get("finish_reason") == "length":
        raise RuntimeError(
            "truncated: thinking+answer hit the token budget — raise max_tokens "
            f"(got {len(content)} content chars)")
    return content


def _strip_think(text):
    return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()


def _parse_sections(md):
    """Split '## Header' markdown into {header: body}."""
    out, cur, buf = {}, None, []
    for line in md.splitlines():
        m = re.match(r"^##\s+(.*)", line.strip())
        if m:
            if cur is not None:
                out[cur] = "\n".join(buf).strip()
            cur, buf = m.group(1).strip(), []
        elif cur is not None:
            buf.append(line)
    if cur is not None:
        out[cur] = "\n".join(buf).strip()
    return out


def main(dirs):
    for d in dirs:
        d = pathlib.Path(d)
        seed_p = d / "material_seed.json"
        if not seed_p.exists():
            print(f"!! {d}: no material_seed.json")
            continue
        seed = json.loads(seed_p.read_text())
        user = ("Here are the ground-truth measurements for this clip:\n\n"
                + _facts(seed)
                + "\n\nWrite the learning material now, following every rule and "
                  "using the exact section headers.")
        print(f".. generating for {d.name} (Qwen) ...", flush=True)
        md = _strip_think(_call_qwen(SYSTEM, user))
        (d / "material.md").write_text(md + "\n")
        sections = _parse_sections(md)
        (d / "material.json").write_text(json.dumps({
            "object_name": seed.get("object_name"),
            "scene_title": seed.get("scene_title"),
            "sections": sections,
        }, indent=2))
        nwords = len(md.split())
        miss = [h for h in SECTIONS if h not in sections]
        print(f"OK {d.name}: material.md ({nwords} words, {len(sections)} sections"
              + (f", MISSING {miss}" if miss else "") + ")")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1:])
