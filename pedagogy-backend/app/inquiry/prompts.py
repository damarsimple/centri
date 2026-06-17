"""Staged-inquiry prompt builders, grounded in the knowledge graph + few-shot testsets.

Mirrors fastapi-gpt's staged Socratic approach (problem-finding → problem-exploring
stage 1 = object → stage 2 = measured data → problem-generating) but built cleanly on
our own assets. Ability band maps to the KG's difficulty rules.
"""
from .. import knowledge, misconceptions
from . import testsets

_LANG = {"en": "English", "id": "Bahasa Indonesia"}
_BAND_DIFFICULTY = {"high": "advanced", "medium": "intermediate",
                    "low": "easy", "neutral": "intermediate"}


def _lang_label(language):
    return _LANG.get((language or "en").lower(), "English")


def difficulty_for(band):
    return _BAND_DIFFICULTY.get((band or "neutral").lower(), "intermediate")


def _measurement_ctx(m):
    return (
        "Measured from the student's own video during the steady phase: "
        f"radius r = {m.radius_m} m, angular velocity w = {m.mean_omega_rad_s} rad/s, "
        f"centripetal acceleration a = {m.mean_ac_m_s2} m/s^2, period T = {m.period_s} s."
    )


_LATEX = (
    "Write EVERY mathematical expression, variable, symbol and equation as inline LaTeX "
    "between single dollar signs — e.g. $a_c = \\omega^2 r$, $v = \\dfrac{2\\pi r}{T}$, "
    "$\\omega$, $r$, $a_c$, $T$. Use LaTeX commands (\\omega, \\pi, \\dfrac, ^, _); never "
    "unicode math symbols like the squared sign, the omega glyph, or the times sign."
)


def problem_finding_generate_messages(band, language, topic):
    difficulty = difficulty_for(band)
    system = (
        "You are a Socratic physics inquiry tutor for circular motion. You generate ONE short "
        "question that prompts the student to FIND or identify an example of circular motion in "
        "their own surroundings. Do not explain the physics — prompt discovery only.\n\n"
        + knowledge.grounding_block("problem_finding", difficulty)
    )
    user = (
        f"Topic: {topic}\n"
        f"Write the inquiry in {_lang_label(language)}. 10-20 words, end with '?'. Prompt the "
        "student to look around and identify something where a point follows a circular path. "
        "Output ONLY the question text."
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}], difficulty


def stage1_generate_messages(object_label, band, language, topic):
    difficulty = difficulty_for(band)
    facts = knowledge.object_facts(object_label)
    fact_lines = ""
    if facts:
        fact_lines = "Known facts about this object:\n" + "\n".join(
            f"- {f}" for f in facts.get("facts", []))
    system = (
        "You are a Socratic physics inquiry tutor for circular motion. You generate ONE short "
        "guiding question (an 'inquiry') that leads a student to discover a concept by observing "
        "a real object. Never give away the answer.\n\n"
        + knowledge.grounding_block("problem_exploring", difficulty)
    )
    user = (
        f"Topic: {topic}\n"
        f"The student is observing this real object: '{object_label}'.\n"
        f"{fact_lines}\n\n"
        f"Write the inquiry in {_lang_label(language)}. 10-20 words, end with '?', refer to the "
        "object, and probe ONE conceptual relationship. Output ONLY the question text.\n\n"
        "Examples of good staged inquiry:\n"
        + testsets.fewshot_block(testsets.stage1_rows(), limit=4)
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}], difficulty


def stage2_generate_messages(measurement, band, language, topic):
    difficulty = difficulty_for(band)
    graph_facts = knowledge.graph_pattern_facts()
    system = (
        "You are a Socratic physics inquiry tutor for circular motion. You generate ONE guiding "
        "question about the relationships in the student's measured data, leading them to reason "
        "about how the quantities relate. Never give away the answer.\n\n"
        + knowledge.grounding_block("problem_exploring", difficulty)
        + "\n\nRELATIONSHIPS available in the data:\n"
        + "\n".join(f"- {f}" for f in graph_facts[:6])
        + "\n\n" + _LATEX
    )
    user = (
        f"Topic: {topic}\n{_measurement_ctx(measurement)}\n\n"
        f"Write the inquiry in {_lang_label(language)}. 12-25 words, end with '?'. Focus on the "
        "relationship between angular velocity, radius, and centripetal acceleration in THEIR "
        "data. Output ONLY the question text.\n\n"
        "Examples:\n" + testsets.fewshot_block(testsets.stage2_rows(), limit=4)
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}], difficulty


def problem_generating_messages(measurement, object_label, band, language, topic):
    """Final stage: author a solvable physics problem from the student's data + object."""
    difficulty = difficulty_for(band)
    obj = object_label or "the rotating object"
    system = (
        "You are a physics problem author for circular motion. You write ONE solvable, "
        "self-contained physics problem grounded in the student's own measured data and object. "
        "It must be a calculable problem (not a reflection question), solvable from the stated "
        "values.\n\n"
        + knowledge.grounding_block("problem_generating", difficulty)
        + "\n\nFormulas you may use:\n"
        + "\n".join(f"- {f}" for f in knowledge.formulas())
    )
    user = (
        f"Topic: {topic}\nObject observed: {obj}.\n{_measurement_ctx(measurement)}\n\n"
        f"Write in {_lang_label(language)}. Return ONLY this JSON (no prose, no code fence):\n"
        '{"problem": "<a solvable problem stem that uses the data above>", '
        '"answer": "<final numeric answer with unit>", '
        '"solution": "<short worked solution>"}\n\n'
        + _LATEX
        + " IMPORTANT: this is JSON, so write each LaTeX backslash doubled inside the "
        "strings (e.g. \"$\\\\omega^2 r$\", \"$\\\\dfrac{2\\\\pi r}{T}$\") so the JSON stays valid."
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}], difficulty


def submit_feedback_messages(inquiry, user_answer, object_label, measurement, language,
                             prior_misconceptions, covered_concepts=None):
    system = (
        "You are a Socratic physics inquiry tutor for circular motion. You evaluate a student's "
        "answer to an inquiry and respond with brief feedback and a next step. RULES: never reveal "
        "the full answer; if the answer is wrong, nudge without giving it away; be encouraging and "
        "concise.\n\n" + knowledge.grounding_block("problem_exploring")
    )
    miscon_note = ""
    if prior_misconceptions:
        miscon_note = ("This student previously showed these misconceptions: "
                       + ", ".join(prior_misconceptions) + ". Watch for them.\n")
    coverage_note = ""
    if covered_concepts:
        coverage_note = ("Concept signals already present in the answer: "
                         + ", ".join(covered_concepts) + ".\n")
    ctx = ""
    if measurement and measurement.mean_omega_rad_s is not None:
        ctx = (f"Their data: r={measurement.radius_m} m, w={measurement.mean_omega_rad_s} rad/s, "
               f"a={measurement.mean_ac_m_s2} m/s^2.\n")
    user = (
        f"Inquiry asked: {inquiry}\n"
        f"Student answer: {user_answer}\n"
        f"Object: {object_label}\n{ctx}{miscon_note}{coverage_note}"
        f"Misconception ids you may detect: {misconceptions.describe_list()}.\n\n"
        f"Respond in {_lang_label(language)}. Return ONLY this JSON (no prose, no code fence):\n"
        '{"is_correct": true|false, "feedback": "<1-2 sentences, do not reveal the answer>", '
        '"next_step": "<one concrete next thinking step>", '
        '"detected_misconception": "<one id from the list, or null>"}\n\n'
        + _LATEX
        + " (This is JSON — double every LaTeX backslash inside the strings so it stays valid.)"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]
