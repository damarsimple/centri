"""Few-shot testset loading (ported from fastapi-gpt origin/development).

Each JSONL row: topic, stage, input, information_1, system_q, user_answer_type,
user_a, system_feedback, scaffolding_or_next_step. Examples are bilingual (EN/ID).
"""
import json
from functools import lru_cache

from .. import config


@lru_cache(maxsize=2)
def _load(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def stage1_rows():
    return _load(str(config.TESTSET_STAGE1_PATH))


def stage2_rows():
    return _load(str(config.TESTSET_STAGE2_PATH))


def fewshot_block(rows, limit=6):
    """Render testset rows as few-shot examples for a prompt."""
    out = []
    for r in rows[:limit]:
        out.append(
            f"Example (object/context: {r.get('input', '')}):\n"
            f"  Inquiry: {r.get('system_q', '')}\n"
            f"  Student answer [{r.get('user_answer_type', '')}]: {r.get('user_a', '')}\n"
            f"  Feedback: {r.get('system_feedback', '')}\n"
            f"  Next step: {r.get('scaffolding_or_next_step', '')}"
        )
    return "\n\n".join(out)
