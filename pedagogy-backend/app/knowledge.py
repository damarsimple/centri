"""Knowledge-graph access for grounding inquiry prompts.

The graph (data/knowledge_graphs/centripetal_acceleration.json) carries the real
pedagogy structure: core_concepts, per-concept formulas/facts, an objects map,
graph_patterns, stage_rules, difficulty_rules, and misconceptions_by_stage.
"""
import json
from functools import lru_cache

from . import config


@lru_cache(maxsize=1)
def load_kg():
    with open(config.KNOWLEDGE_GRAPH_PATH, encoding="utf-8") as f:
        return json.load(f)


def core_concepts():
    return load_kg().get("core_concepts", [])


def object_facts(object_label):
    """Find the KG object entry matching a detected label (by key or keyword)."""
    objects = load_kg().get("objects", {})
    label = (object_label or "").lower().strip()
    if not label:
        return None
    if label in objects:
        return objects[label]
    for name, entry in objects.items():
        candidates = [name.lower().replace("_", " ")] + [k.lower() for k in entry.get("keywords", [])]
        if any(c in label or label in c for c in candidates):
            return entry
    return None


def stage_rules(stage):
    """stage in {problem_finding, problem_exploring, problem_generating}."""
    return load_kg().get("stage_rules", {}).get(stage, [])


def difficulty_rules(difficulty):
    return load_kg().get("difficulty_rules", {}).get((difficulty or "").lower(), [])


def misconceptions_for_stage(stage):
    return load_kg().get("misconceptions_by_stage", {}).get(stage, [])


def formulas():
    ca = load_kg().get("concepts", {}).get("centripetal_acceleration", {})
    return ca.get("formulas", [])


def graph_pattern_facts():
    """All graph-relationship facts, for stage-2 (data-reasoning) grounding."""
    out = []
    for entry in load_kg().get("graph_patterns", {}).values():
        out += entry.get("facts", [])
    return out


def grounding_block(stage="problem_exploring", difficulty=None):
    """Compact, prompt-ready grounding: core concepts + stage/difficulty rules + misconceptions."""
    kg = load_kg()
    parts = ["CORE CONCEPTS (never contradict these):"]
    parts += [f"- {c}" for c in kg.get("core_concepts", [])]

    rules = stage_rules(stage)
    if rules:
        parts.append(f"\nINQUIRY RULES for {stage}:")
        parts += [f"- {r}" for r in rules]

    if difficulty:
        drules = difficulty_rules(difficulty)
        if drules:
            parts.append(f"\nDIFFICULTY ({difficulty}):")
            parts += [f"- {r}" for r in drules]

    misc = misconceptions_for_stage(stage)
    if misc:
        parts.append("\nMISCONCEPTIONS to probe (do not reinforce):")
        parts += [f"- {m}" for m in misc]

    return "\n".join(parts)
