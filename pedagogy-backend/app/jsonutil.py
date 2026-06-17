"""Extract the first JSON object/array from LLM text (robust to code fences and prose)."""
import json
import re


def _strip_fence(text):
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", text or "")
    return fenced.group(1) if fenced else (text or "")


def _loads(s):
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        return None


def first_object(text):
    cand = _strip_fence(text)
    m = re.search(r"\{[\s\S]*\}", cand)
    return _loads(m.group(0)) if m else None


def first_array(text):
    cand = _strip_fence(text)
    m = re.search(r"\[[\s\S]*\]", cand)
    data = _loads(m.group(0)) if m else None
    return data if isinstance(data, list) else None
