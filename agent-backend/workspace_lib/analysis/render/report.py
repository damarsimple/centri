"""Seeded, deterministic LaTeX report generator (run, don't re-author).

Writing the report `.tex` by hand was the agent's single most fragile task. Two
failures recurred every few jobs:

  * **Images silently missing from the PDF.** `compile_latex.sh` does `cd` into the
    report dir, so a hand-written `\\includegraphics{plots/foo.png}` resolved to
    `report/plots/foo.png` (nonexistent). pdflatex does not error on a missing
    graphic — it ships a blank box — so the job "succeeded" with imageless PDFs.
  * **Garbage macros.** The agent hand-substituted stats it didn't guard for null,
    emitting e.g. `\\newcommand{\\OmegaIncStart}{\\SI{N/A}{rad/s}}` (invalid).

Both are mechanical, so the `.tex` is generated here from `stats.json` +
`questions.json`. `\\graphicspath` is set so graphics resolve no matter the compile
CWD, every value is null-guarded, and all human text is LaTeX-escaped. The agent's
job relaxes to: run this, compile, look at the preview PNGs, only patch prose if it
reads wrong. It must NOT re-author the document or move the graphics paths.

    python -m analysis.render.report     # writes student_edition.tex + teacher_key.tex
"""
from __future__ import annotations

import json
import math
import os
import re

# Questions (Subagent C) are gated off the deliverable by default — the artifact is the
# learning MATERIAL. Flip PI_RENDER_QUESTIONS=1 to restore the question bank in the report.
RENDER_QUESTIONS = os.environ.get("PI_RENDER_QUESTIONS", "0") == "1"
from pathlib import Path

from ..common import canonical_omega, dedup_display_name

DATA = Path("analysis_output/data")
REPORT = Path("analysis_output/report")

# Graphics live one level up from the report dir; compile_latex.sh cd's into the
# report dir, so `../plots/` is what resolves. The extra entries make it work
# whether compiled from the report dir, the workspace root, or elsewhere — so a
# missing image becomes impossible the way the old hand-written path made it routine.
GRAPHICS_PATH = r"\graphicspath{{../plots/}{plots/}{./plots/}{analysis_output/plots/}}"

# Figures embedded in the report, with widths. Only those that exist are included.
FIGURES = [
    ("summary_panel.png", 0.95, "Summary panel: trajectory, angular velocity, "
                                "centripetal acceleration, and key measurements."),
    ("trajectory.png", 0.6, "Trajectory in cropped-video space with the fitted orbit."),
    ("omega_t.png", 0.8, "Angular velocity vs.\\ time, phase regions shaded."),
    ("ac_t.png", 0.8, "Centripetal acceleration vs.\\ time."),
    ("radius_t.png", 0.8, "Orbit radius vs.\\ time."),
    ("v_t.png", 0.8, "Tangential speed vs.\\ time."),
]

# Per-figure metadata (width fraction, caption) for the interleaved layout, where
# artifacts sit inside the learning-material prose instead of a separate dump.
FIG_META = {
    "annotated_image.png": (0.62, "A single video frame with the fitted circular orbit "
                                  "and the radius marked from the centre of rotation."),
    "annotated_image_basic.png": (0.62, "A frame from the video showing the object on its "
                                        "circular path, with the radius marked from the centre."),
    "trajectory_basic.png": (0.55, "The path the object traced — every tracked point falls on "
                                   "one circle."),
    "angle_points_basic.png": (0.62, "How many turns the object has completed as time passes. "
                                     "The shape of the line tells the story: a straight line is a "
                                     "steady spin, a line that bends flatter is slowing down, one "
                                     "that steepens is speeding up."),
    "trajectory.png":  (0.55, "The tracked path in video space with the fitted circular orbit."),
    "omega_t.png":     (0.78, "Angular velocity $\\omega$ vs.\\ time, phase regions shaded."),
    "ac_t.png":        (0.78, "Centripetal acceleration $a_c$ vs.\\ time."),
    "radius_t.png":    (0.70, "Orbit radius vs.\\ time."),
    "v_t.png":         (0.70, "Tangential speed vs.\\ time."),
    "summary_panel.png": (0.92, "Summary panel: the trajectory, $\\omega(t)$, $a_c(t)$, "
                                "and the key measurements brought together."),
}

# Which artifacts belong with which material section, so the PDF reads like ordinary
# learning material (figures/table next to the prose that discusses them). "__TABLE__"
# is the key-measurements table, rendered inline. Any figure absent on disk is skipped.
SECTION_ARTIFACTS = {
    "Scenario":                       ["annotated_image.png"],
    "The variables we measured":      ["__TABLE__"],
    "What the video shows over time": ["omega_t.png", "ac_t.png"],
    "Reading the figures":            ["summary_panel.png", "trajectory.png",
                                       "radius_t.png", "v_t.png"],
}

# Difficulty-tiered artifacts: each tier shows a figure/table set whose visual load
# matches its prose (CLT). Basic = a simplified frame + the bare path, no time-series,
# no numeric table; intermediate = standard frame + one trend + the core table;
# advanced = the full multi-panel set + the full table (with alpha/calibration rows).
# "__TABLE_CORE__"/"__TABLE_FULL__" select the table depth; missing figures are skipped.
# The figure_allowlist fed to the generator (generate_tier_material.py) MUST match these,
# so "Reading the figures" only narrates plots the tier actually shows.
TIER_ARTIFACTS = {
    "basic": {
        "Scenario":                       ["annotated_image_basic.png"],
        "What the video shows over time": ["angle_points_basic.png"],
        "Reading the figures":            ["trajectory_basic.png"],
    },
    "intermediate": {
        "Scenario":                       ["annotated_image.png"],
        "The variables we measured":      ["__TABLE_CORE__"],
        "What the video shows over time": ["omega_t.png"],
        "Reading the figures":            ["trajectory.png"],
    },
    "advanced": {
        "Scenario":                       ["annotated_image.png"],
        "The variables we measured":      ["__TABLE_FULL__"],
        "What the video shows over time": ["omega_t.png", "ac_t.png"],
        # No summary_panel dump — it re-shows every raw plot (incl. the rippled radius) and
        # duplicates the trajectory; the interleaved figures above already carry the story.
        "Reading the figures":            ["trajectory.png"],
    },
}

# Unicode that creeps into LLM-generated question text → pdflatex-safe LaTeX.
_UNICODE = {
    "π": r"$\pi$", "ω": r"$\omega$", "θ": r"$\theta$", "α": r"$\alpha$",
    "β": r"$\beta$", "Δ": r"$\Delta$", "σ": r"$\sigma$", "μ": r"$\mu$",
    "·": r"$\cdot$", "×": r"$\times$", "÷": r"$\div$", "±": r"$\pm$",
    "≈": r"$\approx$", "≤": r"$\leq$", "≥": r"$\geq$", "≠": r"$\neq$",
    "→": r"$\rightarrow$", "°": r"$^\circ$", "√": r"$\sqrt{\,}$",
    "∝": r"$\propto$", "∞": r"$\infty$", "≡": r"$\equiv$", "∴": r"$\therefore$",
    "⟨": r"$\langle$", "⟩": r"$\rangle$", "…": r"\ldots{}",
    "²": r"\textsuperscript{2}", "³": r"\textsuperscript{3}",
    "⁻": r"\textsuperscript{-}", "¹": r"\textsuperscript{1}",
    "₀": r"\textsubscript{0}", "₁": r"\textsubscript{1}", "₂": r"\textsubscript{2}",
    "₃": r"\textsubscript{3}", "ₐ": r"\textsubscript{a}", "ᶜ": r"\textsubscript{c}",
    "“": "``", "”": "''", "‘": "`", "’": "'", "–": "--", "—": "---",
    "−": "-", " ": " ",
}
_SPECIALS = {
    "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
    "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


# Physics subscripts the LLM writes as plain ASCII (a_c, a_t, …). Rendered as real
# math subscripts instead of a literal escaped underscore ("a\_c"). Guarded so a
# filename like "omega_t.png" (letter before, extension after) is NOT matched.
_SUBSCRIPT_TOKENS = {
    "a_c": r"$a_{\mathrm{c}}$", "a_t": r"$a_{\mathrm{t}}$",
    "a_r": r"$a_{\mathrm{r}}$", "v_t": r"$v_{\mathrm{t}}$",
    "v_c": r"$v_{\mathrm{c}}$",
}
_SUBSCRIPT_RE = re.compile(r"(?<![A-Za-z0-9])(?:" + "|".join(_SUBSCRIPT_TOKENS) + r")(?![A-Za-z0-9])")


def tex_escape(s) -> str:
    if s is None:
        return ""
    s = str(s)
    # Protect physics subscript tokens from the char-wise underscore escape, then
    # restore them as math after escaping (sentinels use NUL, never in real text).
    sentinels = {}

    def _stash(m):
        key = f"\x00{len(sentinels)}\x00"
        sentinels[key] = _SUBSCRIPT_TOKENS[m.group(0)]
        return key

    s = _SUBSCRIPT_RE.sub(_stash, s)
    out = []
    for ch in s:
        if ch in _UNICODE:
            out.append(_UNICODE[ch])
        elif ch in _SPECIALS:
            out.append(_SPECIALS[ch])
        else:
            out.append(ch)
    res = "".join(out)
    for key, val in sentinels.items():
        res = res.replace(key, val)
    return res


def num(x, prec=2, sig=3):
    """Plain number string, or 'N/A' when missing — never 'None'/'nan'.

    A fixed decimal count destroys small values: the fan's tangential acceleration
    0.0365 renders as "0.04" — one significant figure, which neither matches the
    worked example the seed builds from the same number nor closes its own
    a_t = alpha*r. When rounding to ``prec`` decimals would leave fewer than two
    significant figures, fall back to ``sig`` of them (the seed's own precision)."""
    if x is None:
        return "N/A"
    try:
        xf = float(x)
    except (TypeError, ValueError):
        return "N/A"
    if xf != xf or xf in (float("inf"), float("-inf")):
        return "N/A"
    if xf and math.floor(math.log10(abs(xf))) + prec + 1 < 2:
        return f"{xf:.{sig}g}"
    return f"{xf:.{prec}f}"


def si(x, prec, unit):
    """`\\SI{v}{unit}` when the value is real, else a plain italic N/A (so a null
    phase boundary degrades gracefully instead of producing `\\SI{N/A}{...}`)."""
    v = num(x, prec)
    return f"\\SI{{{v}}}{{{unit}}}" if v != "N/A" else r"\textit{N/A}"


def _measurements_table(stats, level="full", unreliable=False) -> str:
    """Key-measurements tabular. ``level="core"`` keeps the six routine quantities an
    intermediate passage uses (r, $\\omega$, $a_c$, v, T, f) and drops the peak/
    calibration/angular-acceleration rows, which belong to the advanced tier.
    ``unreliable=True`` (oblique-capture clip) drops the per-instant PEAK row (max a_c is
    the ripple's high point — an artifact) so the table never contradicts the caveat."""
    s, pf = stats["summary"], stats["period_and_frequency"]
    cal, st = stats["calibration"], stats["stable_phase"]
    aa = stats.get("angular_acceleration", {})
    # ONE angular velocity, shared with the seed prose + figures. For a (de)accelerating
    # clip this is the clip-average (mean_omega), labelled so — never the misleading
    # "Stable" label on a spin that is not stable.
    omega_val, omega_is_clip_avg = canonical_omega(stats)
    if level == "core":
        # Intermediate is built on the ANGULAR quantities + a_c = omega^2 r; tangential
        # speed v is de-emphasised at this tier (spec TIER 2), so it is not tabled here.
        omega_lbl = "Angular velocity (clip average)" if omega_is_clip_avg else "Angular velocity"
        rows = [
            # Fitted radius (what v and a_c are built from) so it matches the prose exactly.
            ("Orbit radius", si(cal.get("r_fit_m") or s.get("mean_r_m"), 3, "m")),
            (omega_lbl, si(omega_val, 2, r"rad/s")),
            ("Centripetal acceleration", si(s.get("mean_ac"), 2, r"m/s^2")),
            ("Period", si(pf.get("period_s"), 2, "s")),
            ("Frequency", si(pf.get("frequency_hz"), 2, "Hz")),
        ]
        body = " \\\\\n".join(f"{k} & {v}" for k, v in rows)
        return ("\\begin{tabular}{ll}\n\\toprule\n"
                "\\rowcolor{accent!12}\\textbf{Quantity} & \\textbf{Value} \\\\\n\\midrule\n"
                + body + " \\\\\n\\bottomrule\n\\end{tabular}")
    rows = [
        # Single radius row (A9): the fitted orbit radius v and a_c are built from, with the
        # pixel value + calibration folded in — no separate "Mean orbit radius" row to confuse.
        ("Orbit radius (fitted)", f"{num(cal.get('r_fit_m'), 3)} m "
                                  f"({num(cal.get('r_fit_px'), 1)} px @ "
                                  f"{num(cal.get('px_per_m'), 0)} px/m)"),
        ("Angular velocity (clip average)" if omega_is_clip_avg else "Stable angular velocity",
         si(omega_val, 2, r"rad/s")),
        ("Mean centripetal acceleration", si(s.get("mean_ac"), 2, r"m/s^2")),
        # Max a_c is the per-instant ripple peak — drop it on an oblique clip.
        *([] if unreliable else
          [("Maximum centripetal acceleration", si(s.get("max_ac"), 2, r"m/s^2"))]),
        ("Mean tangential speed", si(s.get("mean_v"), 2, r"m/s")),
        ("Period", si(pf.get("period_s"), 2, "s")),
        ("Frequency", si(pf.get("frequency_hz"), 2, "Hz")),
    ]
    # Non-uniform spins (fan spin-up, turntable coast-down) additionally report the
    # angular acceleration and the tangential acceleration it produces.
    if aa.get("motion_type") in ("accelerating", "decelerating"):
        # SIGNED a_t (A3): re-sign from alpha so an older stats.json holding the magnitude
        # still renders the physically-correct negative in a deceleration (a_t opposes motion).
        alpha_v, a_t_v = aa.get("alpha_rad_s2"), aa.get("a_t_mean_m_s2")
        if isinstance(a_t_v, (int, float)) and isinstance(alpha_v, (int, float)):
            a_t_v = math.copysign(abs(a_t_v), alpha_v)
        rows[1:1] = [
            (f"Motion type", aa["motion_type"].capitalize()),
            ("Angular acceleration", si(aa.get("alpha_rad_s2"), 2, r"rad/s^2")),
            ("Tangential acceleration", si(a_t_v, 2, r"m/s^2")),
            (r"$\omega$ initial $\rightarrow$ final",
             f"{num(aa.get('omega_initial'), 2)} $\\rightarrow$ "
             f"{num(aa.get('omega_final'), 2)} rad/s"),
        ]
    body = " \\\\\n".join(f"{k} & {v}" for k, v in rows)
    return ("\\begin{tabular}{ll}\n\\toprule\n"
            "\\rowcolor{accent!12}\\textbf{Quantity} & \\textbf{Value} \\\\\n\\midrule\n"
            + body + " \\\\\n\\bottomrule\n\\end{tabular}")


def _figures_block() -> str:
    out = []
    for name, width, cap in FIGURES:
        if not (REPORT.parent / "plots" / name).exists():
            continue
        out.append(
            "\\begin{figure}[H]\n  \\centering\n"
            f"  \\includegraphics[width={width}\\textwidth]{{{name}}}\n"
            f"  \\caption{{{cap}}}\n"
            "\\end{figure}")
    return "\n\n".join(out)


_MATERIAL_ORDER = [
    "What these words mean",  # basic-tier definitions foundation (absent in int/adv → filtered out)
    "Scenario",
    "The variables we measured",
    "How the variables are related",
    "What the video shows over time",
    "Reading the figures",
]


def _inline_figure(name: str) -> str:
    """A single captioned figure, or "" if the plot is missing on disk."""
    if not (REPORT.parent / "plots" / name).exists():
        return ""
    width, cap = FIG_META.get(name, (0.8, ""))
    cap_tex = f"  \\caption{{{cap}}}\n" if cap else ""
    return ("\\begin{figure}[H]\n  \\centering\n"
            f"  \\includegraphics[width={width}\\textwidth]{{{name}}}\n"
            f"{cap_tex}\\end{{figure}}")


def _inline_table(stats, level="full", unreliable=False) -> str:
    """The key-measurements table as a captioned, centred float for inline use."""
    return ("\\begin{table}[H]\n  \\centering\n"
            "  \\caption{Key measurements for this scene.}\n  "
            + _measurements_table(stats, level, unreliable) + "\n\\end{table}")


_TABLE_KEYS = {"__TABLE__": "full", "__TABLE_FULL__": "full", "__TABLE_CORE__": "core"}


def _section_artifacts(heading: str, stats, tier=None, unreliable=False) -> str:
    """LaTeX for the figures/table that belong with a material section. When ``tier``
    names a known difficulty tier, its (lighter/heavier) artifact set is used instead
    of the default; otherwise the untiered default applies."""
    amap = TIER_ARTIFACTS.get(tier, SECTION_ARTIFACTS) if tier else SECTION_ARTIFACTS
    out = []
    for key in amap.get(heading, []):
        if key in _TABLE_KEYS:
            tex = _inline_table(stats, _TABLE_KEYS[key], unreliable)
        else:
            tex = _inline_figure(key)
        if tex:
            out.append(tex)
    return ("\n\n" + "\n\n".join(out)) if out else ""


# ── deterministic material.seed blocks (objectives / worked examples / honesty / CYU) ──
# These render straight from material_seed.json, whose numbers are correct BY CONSTRUCTION,
# so the arithmetic-heavy content the LLM must NOT author is typeset here instead. Math
# comes from the seed's pre-authored LaTeX (`formula_tex`/`substitute_tex`) rendered in real
# math mode — NOT through tex_escape (which would turn the backslashes into literal text).

def _load_seed():
    p = DATA / "material_seed.json"
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return None


def _objectives_block(objs) -> str:
    if not objs:
        return ""
    items = "\n".join(f"  \\item {tex_escape(o)}" for o in objs)
    return ("\\subsection*{Learning objectives}\n"
            "After this material you can:\n"
            "\\begin{itemize}[leftmargin=*]\n" + items + "\n\\end{itemize}")


def _relations_block(relations) -> str:
    """Numbered relation list: each formula on its own display-math line with its plain
    meaning, so the relations read as a scannable list instead of a run-on paragraph. Seeded
    LaTeX (`tex`) rendered in real math mode (bypasses tex_escape)."""
    if not relations:
        return ""
    items = []
    for r in relations:
        tex = r.get("tex", "")
        plain = tex_escape(r.get("plain", ""))
        items.append(f"  \\item $\\displaystyle {tex}$ \\\\[2pt] {plain}")
    return ("\\begin{enumerate}[leftmargin=*,itemsep=5pt]\n" + "\n".join(items)
            + "\n\\end{enumerate}")


def _worked_examples_block(examples) -> str:
    """Worked examples in the house Given/Formula/Substitute/Result/Interpret format.
    Intermediate/advanced carry seeded LaTeX (`*_tex`) rendered as display math; basic is
    symbol-free (words + one arithmetic line)."""
    if not examples:
        return ""
    out = ["\\subsection*{Worked examples}"]
    for i, e in enumerate(examples, 1):
        parts = [f"\\noindent\\textbf{{Example {i} — {tex_escape(e.get('title'))}}}\\\\"]
        given = e.get("given")
        if given:
            parts.append(f"\\textit{{Given:}} {tex_escape(given)}")
        ftex, stex = e.get("formula_tex"), e.get("substitute_tex")
        if ftex or stex:
            # Real math mode — the seed's LaTeX is trusted and must bypass tex_escape.
            if ftex:
                parts.append(f"\\[{ftex}\\]")
            if stex:
                parts.append(f"\\[{stex}\\]")
        else:
            # Basic: no symbols — show the formula-in-words and the arithmetic line as text.
            line = tex_escape(e.get("formula") or "")
            sub = tex_escape(e.get("substitute") or "")
            if line or sub:
                parts.append((f"{line}: {sub}" if line else sub) + " \\;$\\Rightarrow$\\; "
                             + tex_escape(e.get("result")))
        res = e.get("result")
        interp = e.get("interpret")
        tail = ""
        if res and (ftex or stex):   # basic already folded result into the line above
            tail += f"\\textbf{{Result:}} {tex_escape(res)}. "
        if interp:
            tail += f"\\textit{{{tex_escape(interp)}}}"
        if tail:
            parts.append(tail)
        out.append("\n\n".join(parts) + "\n\n\\medskip")
    return "\n\n".join(out)


def _honesty_block(text) -> str:
    """Measurement-honesty caveat as a shaded, visually distinct box (Part B section 8)."""
    if not text:
        return ""
    return ("\\par\\medskip\\noindent\n"
            "\\colorbox{accent!8}{%\n"
            "\\begin{minipage}{\\dimexpr\\linewidth-2\\fboxsep\\relax}\n"
            "\\textbf{\\textcolor{accent!70!black}{Measurement honesty.}} "
            + tex_escape(text) + "\n\\end{minipage}}\\par\\medskip")


def _cyu_block(items, bridge=None, with_answers: bool = False) -> str:
    """Check-your-understanding questions plus the one-line tier bridge (Part B section 9).
    The answer key prints ONLY in the teacher edition (``with_answers``): printing it in the
    student edition under each question kills the retrieval-practice value — the student reads
    the answer before attempting it (Part B #2). The teacher key holds the answers."""
    if not items:
        return ""
    rows = []
    for q in items:
        line = f"  \\item {tex_escape(q.get('question'))}"
        ans = q.get("answer")
        if ans and with_answers:
            line += ("\\\\\n  {\\small\\itshape\\color{inkgray}Answer: "
                     + tex_escape(ans) + "}")
        rows.append(line)
    out = ("\\subsection*{Check your understanding}\n"
           "\\begin{enumerate}[leftmargin=*]\n" + "\n".join(rows) + "\n\\end{enumerate}")
    if bridge:
        out += ("\n\n\\par\\medskip\\noindent{\\itshape\\color{accent!70!black} "
                + tex_escape(bridge) + "}")
    return out


# Split a run-on definitions paragraph at each new "term: ..." label — the boundary is a
# sentence end (., em/en dash) then a short label (no colon/period) followed by ": ".
_DEF_SPLIT = re.compile(r"(?<=[.—–])\s+(?=[^:.\n]{1,95}?:\s)")


def _definitions_list(body: str) -> str:
    """Render the basic 'What these words mean' section as a per-term bulleted list (a glossary),
    not one running paragraph. Prefer the model's own line breaks; if it wrote a single paragraph,
    fall back to splitting on the 'term:' boundaries. Each term (text before the first colon) is
    bolded."""
    items = [s.strip() for s in body.split("\n") if s.strip()]
    if len(items) <= 1:
        items = [s.strip() for s in _DEF_SPLIT.split(body) if s.strip()]
    lines = ["\\begin{itemize}[leftmargin=*]"]
    for it in items:
        m = re.match(r"([^:]{1,95}?):\s*(.*)", it, re.S)
        if m:
            lines.append(f"  \\item \\textbf{{{tex_escape(m.group(1).strip())}:}} "
                         f"{tex_escape(m.group(2).strip())}")
        else:
            lines.append(f"  \\item {tex_escape(it)}")
    lines.append("\\end{itemize}")
    return "\n".join(lines)


def _material_block(material, stats=None, unreliable=False, seed=None, with_answers=False) -> str:
    """Render Subagent D's grounded learning passage (material.json sections), with
    the relevant figures and the measurements table interleaved into each section so
    the document reads like ordinary learning material rather than prose then a figure
    dump. Pass ``stats`` to enable interleaving; omit it for prose only."""
    if not material:
        return ""
    sections = material.get("sections", material) if isinstance(material, dict) else {}
    if not isinstance(sections, dict) or not sections:
        return ""
    # A tiered material.json carries "tier": basic|intermediate|advanced, which selects
    # the difficulty-matched figure/table set; untiered material keeps the default set.
    tier = material.get("tier") if isinstance(material, dict) else None
    # Deterministic seed blocks keyed by this tier (fall back to a flat block for untiered).
    def _seed_for(key):
        blk = (seed or {}).get(key)
        if isinstance(blk, dict):
            return blk.get(tier) if tier else None
        return blk
    objectives = _objectives_block(_seed_for("objectives"))
    relations = _relations_block(_seed_for("relations_display"))
    worked = _worked_examples_block(_seed_for("worked_examples"))
    honesty = _honesty_block(_seed_for("measurement_honesty"))
    cyu = _cyu_block(_seed_for("check_understanding"), _seed_for("tier_bridge"), with_answers)

    ordered = [h for h in _MATERIAL_ORDER if h in sections]
    ordered += [h for h in sections if h not in _MATERIAL_ORDER]  # tolerate extras
    out = []
    if objectives:                       # canonical skeleton §2: objectives before Scenario
        out.append(objectives)
    worked_done = False
    for h in ordered:
        body = (sections.get(h) or "").strip()
        if not body:
            continue
        block = f"\\subsection*{{{tex_escape(h)}}}\n"
        if h == "What these words mean":
            # Basic-tier definitions render as a per-term glossary list, not a wall of prose.
            block += _definitions_list(body)
        else:
            paras = [tex_escape(p.strip()) for p in re.split(r"\n\s*\n", body) if p.strip()]
            # Lead the relations section with the scannable numbered formula list, then the prose.
            if h == "How the variables are related" and relations:
                block += relations + "\n\n"
            block += "\n\n".join(paras)
        if stats is not None:
            block += _section_artifacts(h, stats, tier, unreliable)
        out.append(block)
        # §6 worked examples sit right after the concepts/relations section.
        if h == "How the variables are related" and worked:
            out.append(worked); worked_done = True
    if worked and not worked_done:       # relations section absent — don't drop the examples
        out.append(worked)
    if honesty:                          # §8 honesty box, then §9 CYU + tier bridge
        out.append(honesty)
    if cyu:
        out.append(cyu)
    return "\n\n".join(out)


# Per-tier accent colour (basic = calm green, intermediate = blue, advanced = deep
# purple); untiered/legacy reports use a neutral teal. Drives headings, rules, the
# level badge and the table header tint, so difficulty reads at a glance.
_TIER_ACCENT = {"basic": "2E7D32", "intermediate": "1565C0", "advanced": "6A1B9A"}
_DEFAULT_ACCENT = "00695C"


def _preamble(tier=None) -> str:
    accent = _TIER_ACCENT.get(tier, _DEFAULT_ACCENT)
    return (
        "\\documentclass[11pt]{article}\n"
        "\\usepackage[T1]{fontenc}\n"
        "\\usepackage[utf8]{inputenc}\n"
        # Libertinus: one cohesive modern book family — Libertinus Serif body, Libertinus Sans
        # headings/masthead (\\sffamily), and matching Libertinus math (libertinust1math) so the
        # prose, the accent headings and every formula share one design language. Needs
        # texlive-fonts-extra in the worker image (added to the Dockerfile).
        "\\usepackage{libertinus}\n"
        "\\usepackage{libertinust1math}\n"
        # Scalable outline font, so microtype EXPANSION is safe (the old expansion=false was
        # only needed for the bitmap Computer Modern default).
        "\\usepackage[protrusion=true,expansion=true]{microtype}\n"
        "\\usepackage[table,dvipsnames]{xcolor}\n"
        "\\usepackage{siunitx}\n\\usepackage{graphicx}\n\\usepackage{booktabs}\n"
        "\\usepackage{amsmath}\n\\usepackage{geometry}\n\\usepackage{hyperref}\n"
        "\\usepackage{enumitem}\n\\usepackage{float}\n\\usepackage{caption}\n"
        "\\usepackage{titlesec}\n\\usepackage{setspace}\n\\usepackage{fixltx2e}\n"
        "\\geometry{margin=1in}\n"
        f"\\definecolor{{accent}}{{HTML}}{{{accent}}}\n"
        "\\definecolor{inkgray}{HTML}{555555}\n"
        f"{GRAPHICS_PATH}\n"
        "\\sisetup{per-mode=symbol}\n"
        "\\setstretch{1.08}\n"
        "\\renewcommand{\\arraystretch}{1.25}\n"
        "\\hypersetup{colorlinks=true,linkcolor=accent,urlcolor=accent}\n"
        # accent sans-serif headings; a thin accent rule trails each \section
        "\\titleformat{\\section}{\\sffamily\\Large\\bfseries\\color{accent}}{}{0em}{}"
        "[{\\vspace{2pt}{\\color{accent!35}\\titlerule[1.2pt]}}]\n"
        "\\titleformat{\\subsection}{\\sffamily\\large\\bfseries\\color{accent!88!black}}{}{0em}{}\n"
        "\\titlespacing*{\\section}{0pt}{1.5em}{0.6em}\n"
        "\\titlespacing*{\\subsection}{0pt}{1.0em}{0.35em}\n"
        "\\captionsetup{font=small,labelfont={bf,color=accent!65!black},labelsep=period}\n"
        "\\begin{document}\n")


def _titleblock(title: str, scene: str, tier=None) -> str:
    """Styled masthead: an accent rule, the title in large sans, then a difficulty
    badge (when tiered) and the scene, closed by a thin rule."""
    badge = ""
    if tier in _TIER_ACCENT:
        badge = ("\\colorbox{accent}{\\textcolor{white}{\\sffamily\\bfseries\\small~"
                 + tier.upper() + " DIFFICULTY~}}")
    scene_tex = (f"\\textcolor{{inkgray}}{{\\sffamily {tex_escape(scene)}}}" if scene else "")
    sub = (f"\\noindent {badge}\\hfill {scene_tex}\\\\[3pt]\n"
           if (badge or scene_tex) else "")
    return (
        "\\noindent{\\color{accent}\\rule{\\linewidth}{2.5pt}}\\\\[3pt]\n"
        f"\\noindent{{\\sffamily\\bfseries\\LARGE\\color{{accent!85!black}} {title}}}\\\\[5pt]\n"
        f"{sub}"
        "\\noindent{\\color{accent!35}\\rule{\\linewidth}{0.6pt}}\\\\[8pt]\n")


def _header_block(stats, learning: bool = False) -> str:
    s, trk = stats["summary"], stats["tracking"]
    vi = stats["video_info"]
    if learning:
        # Learning-material edition: physics context only — no coverage/fps/tracking
        # scaffolding (extraneous cognitive load; not part of the lesson).
        bits = [
            f"\\textbf{{Object:}} {tex_escape(stats.get('object_name'))}",
            f"\\textbf{{Direction:}} {tex_escape(s.get('rotation_direction'))}",
            f"\\textbf{{Clip length:}} {num(vi.get('duration_s'), 1)}\\,s",
        ]
    else:
        bits = [
            f"\\textbf{{Object:}} {tex_escape(stats.get('object_name'))}",
            f"\\textbf{{Rotation:}} {tex_escape(s.get('rotation_direction'))}",
            f"\\textbf{{Coverage:}} {num(trk.get('coverage_pct'), 1)}\\%",
            f"\\textbf{{Duration:}} {num(trk.get('active_duration_s'), 2)}\\,s "
            f"@ {num(vi.get('fps'), 2)}\\,fps",
        ]
    sep = " \\;{\\color{accent!45}\\textbar}\\; "
    return ("\\noindent\\textcolor{inkgray}{\\small\\sffamily "
            + sep.join(bits) + "}\\\\[6pt]\n")


def _flags_block(stats) -> str:
    flags = stats.get("validation_flags") or []
    if not flags:
        return "No data-quality flags were raised."
    return "Validation flags raised: " + ", ".join(tex_escape(f) for f in flags)


# P-MAGIC difficulty tiers, rendered in this order.
_LEVEL_ORDER = ["easy", "intermediate", "advanced"]


def _questions_block(questions, with_answers: bool) -> str:
    # Group by difficulty (easy -> intermediate -> advanced); anything without a
    # recognised level (incl. legacy bloom-tagged questions) falls under "other".
    groups = {}
    for q in questions:
        lvl = (q.get("difficulty") or "other").lower()
        groups.setdefault(lvl, []).append(q)
    order = ([l for l in _LEVEL_ORDER if l in groups] +
             [l for l in groups if l not in _LEVEL_ORDER])

    sections = []
    for lvl in order:
        items = []
        for q in groups[lvl]:
            # App reads `stem`; legacy/report data may carry `question` instead.
            stem = tex_escape(q.get("stem") or q.get("question", ""))
            fmt = q.get("format")
            line = f"  \\item {stem}"
            if fmt:
                line += f" \\textit{{[{tex_escape(fmt)}]}}"
            if with_answers:
                ans = tex_escape(q.get("answer", ""))
                extra = [f"\n  \\textbf{{Answer:}} {ans}"]
                sol = q.get("solution")
                if sol:
                    extra.append(f"\\\\\n  \\textit{{Solution:}} {tex_escape(sol)}")
                hints = q.get("hints") or []
                if hints:
                    hl = "; ".join(tex_escape(h) for h in hints)
                    extra.append(f"\\\\\n  \\textit{{Hints:}} {hl}")
                line += "".join(extra)
            items.append(line)
        if not items:
            continue
        heading = lvl.capitalize() if lvl != "other" else "Questions"
        sections.append(
            f"\\subsection*{{{tex_escape(heading)}}}\n"
            "\\begin{enumerate}[leftmargin=*]\n" + "\n".join(items) +
            "\n\\end{enumerate}")
    return "\n".join(sections)


def _build(stats, questions, *, scene, with_answers: bool, material=None,
           unreliable: bool = False) -> str:
    tier = material.get("tier") if isinstance(material, dict) else None
    # With material, the figures/table are interleaved into the prose (textbook-style),
    # so we drop the separate Key Measurements / Visual Analysis dumps. Without material,
    # fall back to the standalone data + figures sections so nothing is lost.
    seed = _load_seed()   # deterministic worked-examples / CYU / honesty ingredients
    material_tex = _material_block(material, stats, unreliable, seed, with_answers)
    # The student edition of a tiered job IS the learning material: a clean, student-facing
    # lesson — no report framing, no data-quality flags, no questions (those live in the
    # teacher key / a separate worksheet). The teacher key keeps the full report.
    learning = bool(material_tex) and not with_answers
    if with_answers:
        title = "Circular Motion Analysis — Teacher Key"
    elif learning:
        title = "Circular Motion — Learning Material"
    else:
        title = "Circular Motion Analysis Report"
    parts = [
        _preamble(tier),
        _titleblock(title, scene, tier),
        _header_block(stats, learning=learning),
    ]
    if material_tex:
        # The grounded learning passage (with its inline figures/table) leads the document.
        # In learning mode the masthead already says "Learning Material" — no extra heading.
        if not learning:
            parts.append("\n\\section*{Learning Material}\n")
        parts.append(material_tex)
    else:
        parts += [
            "\n\\section*{Key Measurements}\n",
            _measurements_table(stats),
            "\n\\section*{Visual Analysis}\n",
            _figures_block(),
        ]
    # Data-quality notes are for the instructor only (measurement caveats), never on the
    # student learning material.
    if with_answers:
        parts += ["\n\\section*{Data Quality Notes}\n", _flags_block(stats)]
    # Questions are gated OFF by default — the deliverable is the learning MATERIAL, not a
    # worksheet (Subagent C). Set PI_RENDER_QUESTIONS=1 to bring the question bank back
    # (e.g. for a P-MAGIC question comparison); the generator code stays intact.
    if RENDER_QUESTIONS and questions:
        parts += ["\n\\section*{Questions}\n", _questions_block(questions, with_answers)]
    parts.append("\n\\end{document}\n")
    return "\n".join(parts)


def _load_material():
    mpath = DATA / "material.json"
    if not mpath.exists():
        return None
    try:
        return json.loads(mpath.read_text())
    except (ValueError, OSError):
        return None


_TIERS = ("basic", "intermediate", "advanced")


def _load_tiers():
    """Return {tier: material} for every material.<tier>.json present (difficulty-tiered
    path). Empty dict when the job is untiered (legacy single material.json)."""
    out = {}
    for t in _TIERS:
        p = DATA / f"material.{t}.json"
        if p.exists():
            try:
                out[t] = json.loads(p.read_text())
            except (ValueError, OSError):
                pass
    return out


def _emit(stats, questions, scene, material, *, suffix="", unreliable=False):
    """Write student_edition{suffix}.tex + teacher_key{suffix}.tex for one material."""
    student = _build(stats, questions, scene=scene, with_answers=False,
                     material=material, unreliable=unreliable)
    teacher = _build(stats, questions, scene=scene, with_answers=True,
                     material=material, unreliable=unreliable)
    (REPORT / f"student_edition{suffix}.tex").write_text(student)
    (REPORT / f"teacher_key{suffix}.tex").write_text(teacher)
    return student.count("\\includegraphics")


def _is_unreliable(stats) -> bool:
    """Per-instant omega an oblique-capture artifact? Drives table/figure hedging."""
    try:
        from .. import quality_signals
        sig = quality_signals.compute(DATA / "kinematics.csv", stats)
        return "per_instant_omega_unreliable" in sig.get("flags", [])
    except Exception:
        return False


def main() -> int:
    REPORT.mkdir(parents=True, exist_ok=True)
    stats = json.loads((DATA / "stats.json").read_text())
    qpath = DATA / "questions.json"
    questions = json.loads(qpath.read_text()) if qpath.exists() else []
    if isinstance(questions, dict):  # tolerate {"questions": [...]} shape
        questions = questions.get("questions", [])
    # De-duplicate the "<X> on <X>" scene title that arises when the tracked label
    # equals the reference label (e.g. "black ball on black ball" -> "black ball").
    scene = dedup_display_name(stats.get("scene_title") or stats.get("object_name"))
    unreliable = _is_unreliable(stats)

    tiers = _load_tiers()
    if tiers:
        # Difficulty-tiered path: one PDF pair per tier (suffix .basic / .intermediate / ...).
        for tier, material in tiers.items():
            n_fig = _emit(stats, questions, scene, material, suffix=f".{tier}",
                          unreliable=unreliable)
            n_mat = len(material.get("sections", {}))
            print(f"REPORT OK [{tier}] — student_edition.{tier}.tex + teacher_key.{tier}.tex "
                  f"({n_mat} material sections, {n_fig} figures)")
        print(f"REPORT OK — {len(tiers)} tier(s) rendered ({len(questions)} questions, "
              f"scene='{scene}')")
        return 0

    # Legacy / untiered single material.json.
    material = _load_material()
    n_fig = _emit(stats, questions, scene, material, unreliable=unreliable)
    n_mat = len((material or {}).get("sections", {})) if material else 0
    print(f"REPORT OK — student_edition.tex + teacher_key.tex written "
          f"({len(questions)} questions, {n_mat} material sections, "
          f"{n_fig} figures, scene='{scene}')")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
