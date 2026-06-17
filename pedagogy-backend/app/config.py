"""Configuration for the pedagogy backend.

Reads from environment (see .env.example). The LLM points at the same Qwen
llama.cpp server the measurement backend uses; nothing here is hardcoded-secret.
"""
import os
import pathlib

try:
    from dotenv import load_dotenv
    load_dotenv()
except ModuleNotFoundError:
    # python-dotenv is optional; env vars are still read via os.getenv below.
    pass

# ── LLM (OpenAI-compatible llama.cpp server hosting Qwen — shared infra) ──────
LLM_URL = os.getenv("PEDAGOGY_LLM_URL", "http://192.168.1.205:8083/v1")
LLM_KEY = os.getenv("PEDAGOGY_LLM_KEY", "")  # set via env; never commit the token
LLM_MODEL = os.getenv("PEDAGOGY_LLM_MODEL", "Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf")
LLM_TIMEOUT = int(os.getenv("PEDAGOGY_LLM_TIMEOUT", "120"))
LLM_TEMPERATURE = float(os.getenv("PEDAGOGY_LLM_TEMPERATURE", "0.7"))
# Qwen "thinking" mode consumes tokens in reasoning_content; keep headroom so the
# actual answer lands in `content` (same lesson as agent-backend's progress analyzer).
LLM_MAX_TOKENS = int(os.getenv("PEDAGOGY_LLM_MAX_TOKENS", "10000"))

# ── Data assets (ported from fastapi-gpt origin/development) ──────────────────
BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
KNOWLEDGE_GRAPH_PATH = DATA_DIR / "knowledge_graphs" / "centripetal_acceleration.json"
TESTSET_STAGE1_PATH = DATA_DIR / "testsets" / "problem_exploring_stage1.jsonl"
TESTSET_STAGE2_PATH = DATA_DIR / "testsets" / "problem_exploring_stage2.jsonl"

# ── Student-model DB (sqlite for a zero-config own-version start) ─────────────
DB_PATH = os.getenv("PEDAGOGY_DB_PATH", str(BASE_DIR / "pedagogy.db"))

DEFAULT_TOPIC = "centripetal acceleration"

# ── Measurement backend (agent-backend) — to auto-populate the seam ──────────
AGENT_BACKEND_URL = os.getenv("AGENT_BACKEND_URL", "http://140.115.126.111:8082")
AGENT_BACKEND_KEY = os.getenv("AGENT_BACKEND_KEY", "")
