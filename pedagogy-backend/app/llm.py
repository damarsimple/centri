"""Thin OpenAI-compatible chat client for the shared Qwen llama.cpp server."""
import requests

from . import config, jsonutil


class LLMError(RuntimeError):
    pass


def chat(messages, temperature=None, max_tokens=None, timeout=None):
    """Call /v1/chat/completions and return the assistant's text content."""
    url = config.LLM_URL.rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    if config.LLM_KEY:
        headers["Authorization"] = f"Bearer {config.LLM_KEY}"
    payload = {
        "model": config.LLM_MODEL,
        "messages": messages,
        "temperature": config.LLM_TEMPERATURE if temperature is None else temperature,
        "max_tokens": config.LLM_MAX_TOKENS if max_tokens is None else max_tokens,
    }
    try:
        resp = requests.post(
            url, headers=headers, json=payload,
            timeout=config.LLM_TIMEOUT if timeout is None else timeout,
        )
    except requests.RequestException as e:
        raise LLMError(f"LLM request failed: {e}") from e
    if resp.status_code != 200:
        raise LLMError(f"LLM returned {resp.status_code}: {resp.text[:500]}")
    try:
        return resp.json()["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, ValueError) as e:
        raise LLMError(f"Unexpected LLM response shape: {resp.text[:500]}") from e


def chat_json(messages, **kwargs):
    """Call chat() and parse the first JSON object from the reply. Returns (dict|None, raw)."""
    raw = chat(messages, **kwargs)
    return jsonutil.first_object(raw), raw
