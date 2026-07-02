# MiMo Inference Test Report

_Date: 2026-06-12 — **Reverted 2026-06-21**: switched back to local Qwen (`llama.cpp-lab1`, `192.168.1.205:8083`, key `hwanglabyoungdumbandbreak`). See `.env` and `.pi/agent/models.json`._

Tested Xiaomi MiMo platform as a replacement for the local Qwen inference server (`192.168.1.205:8083`) for the `pi` agent in the measurement backend.

## Setup

- **API endpoint:** `https://api.xiaomimimo.com/v1` (OpenAI-compatible)
- **API key:** `sk-***...` (user-provided)
- **Test job:** duplicate of `job_6d1108b2` — "red phone on black circular base" (turntable video, 321 frames, 5.35s)
- **Pi CLI provider:** built-in `xiaomi` provider (not a custom models.json entry)

## Results

| Model | Provider | Status | Time | Notes |
|---|---|---|---|---|
| mimo-v2-flash | built-in `xiaomi` | **Done** | **11m 4s** | Fastest |
| mimo-v2.5-pro | custom `mimo` | Done | 16m 52s | Slow — custom config lacked MiMo message formatting |
| mimo-v2-omni | custom `mimo` | Done | 17m 16s | Slow — same reason |
| mimo-v2-flash | custom `mimo` | **Failed** | ~9m | `reasoning: false` in custom config caused `Cannot continue from message role: assistant` after context compaction |

### Physics (identical across all runs — frozen pipeline is deterministic)

| Metric | Value |
|---|---|
| mean ω | 7.37 rad/s |
| mean aᶜ | 9.25 m/s² |
| period | 0.84 s |
| radius | 0.15 m |
| rotation | CCW |
| tracking coverage | 100% |

## Key Findings

1. **MiMo Flash is the fastest** at ~11 min — ~5 min faster than Pro/Omni, and competitive with the local Qwen (~4 min on a good day, but unreliable due to shared-GPU crashes).

2. **Use the built-in `xiaomi` provider**, not a custom models.json entry. The built-in provider handles MiMo's message format correctly (reasoning content, multi-turn tool calls, context compaction). A custom config with incorrect `reasoning: false` caused Flash to fail after context overflow.

3. **All models produce identical physics** — the frozen `analysis/` pipeline is deterministic. The model only affects orchestration speed, not measurement quality.

4. **MiMo Flash previously failed with a custom provider** because:
   - `reasoning` was set to `false` (should be `true` — Flash supports thinking)
   - Custom provider didn't handle MiMo's `reasoning_content` field in multi-turn conversations
   - After context compaction, the message format was incompatible

## Changes Made

| File | Change |
|---|---|
| `.env` | `PI_MODEL=xiaomi/mimo-v2-flash`, `PI_INFERENCE_URL=https://api.xiaomimimo.com`, `XIAOMI_API_KEY=...` |
| `app/llm.py` | Auth header changed to `api-key` (MiMo format) |
| `docker-compose.yml` | Added `XIAOMI_API_KEY` to worker environment |
| `.pi/agent/models.json` | Removed custom `mimo` provider (using built-in instead) |

## Recommendation

MiMo Flash via the built-in `xiaomi` provider is a viable alternative to the local Qwen server. It's slower (~11 min vs ~4 min) but more reliable (no shared-GPU crashes, no model unloading). Worth considering if the Qwen instability continues to be a problem.

**Reverted 2026-06-21:** `PI_MODEL=llama.cpp-lab1/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf`, `PI_INFERENCE_URL=http://192.168.1.205:8083`, key `hwanglabyoungdumbandbreak` in `.pi/agent/models.json`.
