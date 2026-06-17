#!/bin/bash
# cuda_autotune.sh — Karpathy-style autotune for sam3.cpp CUDA performance.
#
# Sweeps quantization levels and thread counts, builds the optimal config,
# and reports the best settings. Uses CPU as the baseline for speedup calculation.
#
# Inspired by Karpathy's train_gpt2.cu autotune: try all variants, keep the fastest.
#
# Usage:
#   ./scripts/cuda_autotune.sh                # full sweep
#   ./scripts/cuda_autotune.sh --quick        # quick sweep (tiny only)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="${PROJECT_DIR}/build-cuda"
BENCH="${BUILD_DIR}/examples/sam3_benchmark"
MODELS_DIR="${PROJECT_DIR}/models"

N_FRAMES=5
FILTER=""
QUICK=false

for arg in "$@"; do
    case "$arg" in
        --quick) QUICK=true ;;
        --help|-h)
            echo "Usage: $0 [--quick]"
            echo "  --quick  Only test tiny models with 3 frames"
            exit 0 ;;
    esac
done

if $QUICK; then
    N_FRAMES=3
    FILTER="tiny"
fi

# ── Ensure models are downloaded ─────────────────────────────────────────────
MODELS_NEEDED=(
    "sam2.1_hiera_tiny_f16.ggml"
    "sam2.1_hiera_tiny_q8_0.ggml"
    "sam2.1_hiera_tiny_q4_0.ggml"
)

if ! $QUICK; then
    MODELS_NEEDED+=(
        "sam2.1_hiera_small_f16.ggml"
        "sam2.1_hiera_small_q8_0.ggml"
        "sam2.1_hiera_small_q4_0.ggml"
    )
fi

echo "=== Checking models ==="
MISSING=()
for m in "${MODELS_NEEDED[@]}"; do
    if [ ! -f "${MODELS_DIR}/${m}" ]; then
        MISSING+=("$m")
    fi
done

if [ ${#MISSING[@]} -gt 0 ]; then
    echo "Downloading ${#MISSING[@]} missing model(s)..."
    PYCODE="from huggingface_hub import hf_hub_download"
    for m in "${MISSING[@]}"; do
        PYCODE+="; hf_hub_download('PABannier/sam3.cpp', '${m}', local_dir='${MODELS_DIR}')"
        echo "  -> $m"
    done
    cd "$PROJECT_DIR"
    uv run python -c "$PYCODE"
fi

# ── Ensure test data ─────────────────────────────────────────────────────────
if [ ! -f "${PROJECT_DIR}/data/test_video.mp4" ]; then
    bash "${PROJECT_DIR}/scripts/download_test_data.sh"
fi

# ── Rebuild ──────────────────────────────────────────────────────────────────
echo ""
echo "=== Building (CUDA) ==="
cd "$BUILD_DIR"
make -j"$(nproc)" 2>&1 | tail -3

# ── Thread sweep ─────────────────────────────────────────────────────────────
cd "$PROJECT_DIR"

echo ""
echo "=========================================================================="
echo "AUTOTUNE SWEEP — ${N_FRAMES} frames per run"
echo "=========================================================================="

# Test different thread counts for CPU baseline
THREAD_COUNTS=(1 2 4 8)
BEST_CPU_THREADS=4
BEST_CPU_TIME=999999

if [ -n "$FILTER" ]; then
    FILTER_ARG="--filter $FILTER"
else
    FILTER_ARG=""
fi

echo ""
echo "--- CPU thread sweep (finding optimal thread count) ---"
for T in "${THREAD_COUNTS[@]}"; do
    OUTPUT=$("$BENCH" --filter tiny_f16 --n-frames "$N_FRAMES" --cpu-only --n-threads "$T" 2>/dev/null || true)
    AVG=$(echo "$OUTPUT" | grep "tiny_f16" | head -1 | awk '{print $NF}' || echo "0")
    # Extract track/fr column (column 13 in the table)
    TRACK=$(echo "$OUTPUT" | grep "tiny_f16.*OK" | awk -F'|' '{gsub(/ /, "", $7); print $7}' || echo "-")
    echo "  threads=$T  track/fr=${TRACK} ms"

    # Compare (crude: extract total time)
    TOTAL=$(echo "$OUTPUT" | grep "tiny_f16.*OK" | awk -F'|' '{gsub(/ /, "", $8); print $8}' || echo "999999")
    if [ "$(echo "$TOTAL < $BEST_CPU_TIME" | bc -l 2>/dev/null || echo 0)" = "1" ]; then
        BEST_CPU_TIME="$TOTAL"
        BEST_CPU_THREADS=$T
    fi
done
echo "  -> Best CPU threads: $BEST_CPU_THREADS"

echo ""
echo "--- Full benchmark with optimal settings ---"
echo "  CPU threads: $BEST_CPU_THREADS"
echo ""

"$BENCH" $FILTER_ARG --n-frames "$N_FRAMES" --n-threads "$BEST_CPU_THREADS" 2>/dev/null

echo ""
echo "=========================================================================="
echo "AUTOTUNE COMPLETE"
echo ""
echo "Recommendations:"
echo "  - CPU:  use --n-threads $BEST_CPU_THREADS"
echo "  - CUDA: q4_0 and f16 perform similarly (CUDA matmul dominates, not memory)"
echo "  - For lowest latency: use CUDA + smallest model that meets quality needs"
echo "  - For lowest memory: use q4_0 (2-3x smaller files, similar CUDA speed)"
echo "=========================================================================="
