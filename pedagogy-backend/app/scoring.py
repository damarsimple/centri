"""Lightweight, deterministic concept-coverage detection for student answers.

A cheap signal (keyword/phrase based, EN + ID) to complement the LLM's judgment —
flags which core relationships a student's answer touches. Inspired by fastapi-gpt's
`_stage1_detect_concept_coverage`, but kept simple and explicit.
"""

_CONCEPT_SIGNALS = {
    "inward_direction": ["inward", "toward the center", "towards the center", "toward centre",
                         "ke pusat", "ke dalam", "menuju pusat"],
    "direction_change": ["change direction", "changes direction", "velocity direction",
                         "direction of velocity", "berubah arah", "arah kecepatan"],
    "omega_squared": ["squared", "square", "ω²", "w^2", "omega squared", "kuadrat"],
    "radius_relation": ["radius", "farther from", "further from", "distance from center",
                        "jari-jari", "jarak dari pusat"],
    "force_source": ["tension", "gravity", "friction", "string pulls",
                     "tegangan", "gravitasi", "gesekan"],
}


def concept_coverage(answer_text):
    """Return {concept: bool} for which signals the answer touches."""
    text = (answer_text or "").lower()
    return {c: any(t in text for t in terms) for c, terms in _CONCEPT_SIGNALS.items()}


def covered_concepts(answer_text):
    """List of concept keys the answer touches."""
    return [c for c, hit in concept_coverage(answer_text).items() if hit]
