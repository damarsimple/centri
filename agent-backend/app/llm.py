"""Minimal synchronous client for the vision LLM (llama.cpp, OpenAI-compatible).

Used by lightweight interactive endpoints (e.g. /suggest-scene) that need a single
fast VLM call — NOT the heavy agentic job pipeline, which goes through the `pi` CLI.
"""
import base64
import json
import os
import re

import requests

INFERENCE_URL = os.environ.get("PI_INFERENCE_URL", "http://192.168.1.205:8083").rstrip("/")
INFERENCE_KEY = os.environ.get("PI_INFERENCE_API_KEY", "")
MODEL = os.environ.get("PI_MODEL", "Qwen3.6-35B-A3B")
# Reasoning model: it emits a long `reasoning_content` budget before the answer.
# Give generous room (it stops on its own once it answers) and a matching timeout.
DEFAULT_TIMEOUT = int(os.environ.get("PI_ANALYZER_TIMEOUT", "300"))
DEFAULT_MAX_TOKENS = int(os.environ.get("PI_VISION_MAX_TOKENS", "100000"))

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def vision_chat(
    image_bytes: bytes,
    prompt: str,
    *,
    mime: str = "image/jpeg",
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = 0.3,
    timeout: int = DEFAULT_TIMEOUT,
) -> str:
    """Send one image + text prompt, return the assistant's text content."""
    b64 = base64.b64encode(image_bytes).decode("ascii")
    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{b64}"},
                    },
                ],
            }
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    headers = {"Content-Type": "application/json"}
    if INFERENCE_KEY:
        headers["api-key"] = INFERENCE_KEY

    resp = requests.post(
        f"{INFERENCE_URL}/v1/chat/completions",
        json=payload,
        headers=headers,
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"] or ""


def strip_reasoning(text: str) -> str:
    """Remove <think>…</think> blocks the reasoning model may emit inline."""
    return _THINK_RE.sub("", text).strip()


def extract_json(text: str) -> dict:
    """Pull the first balanced JSON object out of a model response."""
    cleaned = strip_reasoning(text)
    start = cleaned.find("{")
    if start == -1:
        raise ValueError("no JSON object in model output")
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(cleaned)):
        c = cleaned[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return json.loads(cleaned[start : i + 1])
    raise ValueError("unbalanced JSON object in model output")
