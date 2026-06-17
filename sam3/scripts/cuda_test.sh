#!/bin/bash
# cuda_test.sh — rapid CUDA iteration test harness
#
# Rebuilds (incremental), runs CUDA + CPU on the smallest model, and compares
# detection counts plus rendered preview output.
# Exits non-zero if CUDA crashes, falls back to CPU, or materially differs.
#
# Usage:
#   ./scripts/cuda_test.sh              # default: tiny f16, 3 frames
#   ./scripts/cuda_test.sh --quick      # 2 frames, skip CPU comparison
#   ./scripts/cuda_test.sh --all-quant  # test f16 + q8_0 + q4_0

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="${PROJECT_DIR}/build-cuda"
BENCH="${BUILD_DIR}/examples/sam3_benchmark"
DEMO="${BUILD_DIR}/examples/sam3_demo_track"

N_FRAMES=3
FILTER="tiny_f16"
SKIP_CPU=false
ALL_QUANT=false

trim() {
    local s="$1"
    s="${s#"${s%%[![:space:]]*}"}"
    s="${s%"${s##*[![:space:]]}"}"
    printf '%s' "$s"
}

declare -A CPU_BACKEND CPU_DET
declare -A GPU_BACKEND GPU_DET

parse_benchmark_table() {
    local mode="$1"
    local output="$2"
    local parsed=0

    while IFS='|' read -r _ model _ backend _ _ _ _ det status; do
        model="$(trim "${model:-}")"
        backend="$(trim "${backend:-}")"
        det="$(trim "${det:-}")"
        status="$(trim "${status:-}")"

        if [[ -z "$model" || "$model" == "Model" || -z "$status" ]]; then
            continue
        fi

        if [[ "$status" != OK* ]]; then
            echo "FAIL: benchmark reported failure for ${mode} run (${model} / ${backend}): ${status}" >&2
            return 1
        fi

        if [[ "$mode" == "cpu" ]]; then
            CPU_BACKEND["$model"]="$backend"
            CPU_DET["$model"]="$det"
        else
            GPU_BACKEND["$model"]="$backend"
            GPU_DET["$model"]="$det"
        fi

        parsed=$((parsed + 1))
    done <<< "$output"

    if [[ $parsed -eq 0 ]]; then
        echo "FAIL: could not parse any ${mode} benchmark rows" >&2
        return 1
    fi
}

preview_path() {
    local output_path="$1"
    printf '%s_preview.png' "${output_path%.*}"
}

file_sha256() {
    sha256sum "$1" | awk '{print $1}'
}

run_demo_compare() {
    local model="$1"
    local model_path="${PROJECT_DIR}/models/${model}.ggml"
    local cpu_output="${TMP_DIR}/${model}_cpu.mp4"
    local gpu_output="${TMP_DIR}/${model}_gpu.mp4"
    local cpu_log="${TMP_DIR}/${model}_cpu.log"
    local gpu_log="${TMP_DIR}/${model}_gpu.log"
    local cpu_preview gpu_preview cpu_hash gpu_hash

    if [[ ! -f "$model_path" ]]; then
        echo "FAIL: missing model file for demo comparison: ${model_path}" >&2
        exit 1
    fi

    if ! "$DEMO" --model "$model_path" --video data/test_video.mp4 \
            --n-frames "$N_FRAMES" --output "$cpu_output" --no-gpu \
            > /dev/null 2>"$cpu_log"; then
        echo "FAIL: demo_track CPU run failed for ${model}" >&2
        exit 1
    fi

    if ! "$DEMO" --model "$model_path" --video data/test_video.mp4 \
            --n-frames "$N_FRAMES" --output "$gpu_output" \
            > /dev/null 2>"$gpu_log"; then
        echo "FAIL: demo_track CUDA run failed for ${model}" >&2
        exit 1
    fi

    if ! grep -q '^Backend: CUDA' "$gpu_log"; then
        echo "FAIL: demo_track requested CUDA but did not initialize a CUDA backend for ${model}" >&2
        exit 1
    fi

    cpu_preview="$(preview_path "$cpu_output")"
    gpu_preview="$(preview_path "$gpu_output")"

    if [[ ! -f "$cpu_preview" || ! -f "$gpu_preview" ]]; then
        echo "FAIL: missing preview output for ${model}" >&2
        exit 1
    fi

    cpu_hash="$(file_sha256 "$cpu_preview")"
    gpu_hash="$(file_sha256 "$gpu_preview")"
    if [[ "$cpu_hash" != "$gpu_hash" ]]; then
        echo "FAIL: preview mismatch for ${model}: CPU=${cpu_hash} CUDA=${gpu_hash}" >&2
        exit 1
    fi
}

for arg in "$@"; do
    case "$arg" in
        --quick)   N_FRAMES=2; SKIP_CPU=true ;;
        --all-quant) ALL_QUANT=true; FILTER="tiny" ;;
        --help|-h)
            echo "Usage: $0 [--quick] [--all-quant]"
            echo "  --quick      2 frames, CUDA only (fastest)"
            echo "  --all-quant  test f16 + q8_0 + q4_0"
            exit 0 ;;
    esac
done

TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/sam3_cuda_test.XXXXXX")"
trap 'status=$?; if [[ $status -eq 0 ]]; then rm -rf "$TMP_DIR"; else echo "Artifacts left in $TMP_DIR" >&2; fi' EXIT

# ── Rebuild ──────────────────────────────────────────────────────────────────
echo "=== Rebuilding (incremental) ==="
cd "$BUILD_DIR"
make -j"$(nproc)" 2>&1 | tail -3
echo ""

cd "$PROJECT_DIR"

# ── Check test data ──────────────────────────────────────────────────────────
if [ ! -f data/test_video.mp4 ]; then
    echo "Downloading test data..."
    bash scripts/download_test_data.sh
fi

if [ ! -f "models/sam2.1_hiera_tiny_f16.ggml" ]; then
    echo "ERROR: no tiny model found. Download with:"
    echo "  uv run python -c \"from huggingface_hub import hf_hub_download; hf_hub_download('PABannier/sam3.cpp', 'sam2.1_hiera_tiny_f16.ggml', local_dir='models')\""
    exit 1
fi

# ── Run CUDA ─────────────────────────────────────────────────────────────────
echo "=== CUDA benchmark (${FILTER}, ${N_FRAMES} frames) ==="
if $SKIP_CPU; then
    if ! GPU_OUT=$("$BENCH" --filter "$FILTER" --n-frames "$N_FRAMES" --gpu-only 2>/dev/null); then
        echo ""
        echo "FAIL: CUDA benchmark run failed"
        exit 1
    fi
    parse_benchmark_table gpu "$GPU_OUT"

    for model in "${!GPU_BACKEND[@]}"; do
        if [[ ${GPU_BACKEND[$model]} != CUDA* ]]; then
            echo ""
            echo "FAIL: ${model} requested CUDA but initialized ${GPU_BACKEND[$model]}" >&2
            exit 1
        fi
    done
else
    if ! CPU_OUT=$("$BENCH" --filter "$FILTER" --n-frames "$N_FRAMES" --cpu-only 2>/dev/null); then
        echo ""
        echo "FAIL: CPU benchmark baseline failed"
        exit 1
    fi
    if ! GPU_OUT=$("$BENCH" --filter "$FILTER" --n-frames "$N_FRAMES" --gpu-only 2>/dev/null); then
        echo ""
        echo "FAIL: CUDA benchmark run failed"
        exit 1
    fi

    parse_benchmark_table cpu "$CPU_OUT"
    parse_benchmark_table gpu "$GPU_OUT"

    for model in "${!CPU_BACKEND[@]}"; do
        if [[ -z ${GPU_BACKEND[$model]+x} ]]; then
            echo ""
            echo "FAIL: missing CUDA result for ${model}" >&2
            exit 1
        fi
        if [[ ${GPU_BACKEND[$model]} != CUDA* ]]; then
            echo ""
            echo "FAIL: ${model} requested CUDA but initialized ${GPU_BACKEND[$model]}" >&2
            exit 1
        fi
        if [[ ${CPU_DET[$model]} != ${GPU_DET[$model]} ]]; then
            echo ""
            echo "FAIL: detection count mismatch for ${model}: CPU=${CPU_DET[$model]} CUDA=${GPU_DET[$model]}" >&2
            exit 1
        fi
    done

    echo ""
    echo "=== Preview comparison (${FILTER}, ${N_FRAMES} frames) ==="
    for model in "${!CPU_BACKEND[@]}"; do
        run_demo_compare "$model"
    done
fi

echo ""
echo "=== All tests passed ==="
