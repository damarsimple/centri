#!/usr/bin/env python3
"""
python_cuda_baseline.py — PyTorch inference baseline for SAM2.

Runs the official SAM2 model and reports per-frame latencies, providing a
reference baseline to compare against sam3.cpp performance. CUDA is required
by default; use --cpu only when you intentionally want a CPU comparison.

Usage:
    uv run python scripts/python_cuda_baseline.py [--model tiny] [--n-frames 3]
    uv run python scripts/python_cuda_baseline.py --cpu
"""

import argparse
import time
import sys
import os

import torch
import numpy as np

# Try to import PIL for video frame decoding
try:
    from PIL import Image
except ImportError:
    print("ERROR: pip install Pillow", file=sys.stderr)
    sys.exit(1)

# Try to import sam2
try:
    from sam2.build_sam import build_sam2_video_predictor, build_sam2
    from sam2.sam2_image_predictor import SAM2ImagePredictor
except ImportError:
    print("ERROR: pip install sam2 (or: uv pip install sam-2)", file=sys.stderr)
    sys.exit(1)


MODEL_CONFIGS = {
    "tiny": {
        "config": "configs/sam2.1/sam2.1_hiera_t.yaml",
        "checkpoint": "facebook/sam2.1-hiera-tiny",
    },
    "small": {
        "config": "configs/sam2.1/sam2.1_hiera_s.yaml",
        "checkpoint": "facebook/sam2.1-hiera-small",
    },
    "base_plus": {
        "config": "configs/sam2.1/sam2.1_hiera_b+.yaml",
        "checkpoint": "facebook/sam2.1-hiera-base-plus",
    },
    "large": {
        "config": "configs/sam2.1/sam2.1_hiera_l.yaml",
        "checkpoint": "facebook/sam2.1-hiera-large",
    },
}


def decode_video_frames(video_path, n_frames):
    """Decode video frames using ffmpeg subprocess."""
    import subprocess
    import json

    # Get video info
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_streams", video_path
    ]
    info = json.loads(subprocess.check_output(cmd))
    stream = next(s for s in info["streams"] if s["codec_type"] == "video")
    w, h = int(stream["width"]), int(stream["height"])

    frames = []
    for i in range(n_frames):
        cmd = [
            "ffmpeg", "-i", video_path, "-vf", f"select=eq(n\\,{i})",
            "-vsync", "0", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"
        ]
        raw = subprocess.check_output(cmd, stderr=subprocess.DEVNULL)
        frame = np.frombuffer(raw, dtype=np.uint8).reshape(h, w, 3)
        frames.append(Image.fromarray(frame))

    return frames, w, h


def benchmark_sam2_image(model_name, frames, point_x, point_y, device):
    """Benchmark SAM2 using image predictor (frame-by-frame, closest to sam3.cpp)."""
    cfg = MODEL_CONFIGS[model_name]

    print(f"\n{'='*70}")
    print(f"Python SAM2.1 {model_name} — {device} — {len(frames)} frames")
    print(f"{'='*70}\n")

    # Load model
    t0 = time.perf_counter()
    predictor = SAM2ImagePredictor.from_pretrained(cfg["checkpoint"], device=device)
    t_load = (time.perf_counter() - t0) * 1000
    print(f"  Model load:     {t_load:8.1f} ms")

    # Warmup
    with torch.inference_mode():
        predictor.set_image(np.array(frames[0]))
        _ = predictor.predict(
            point_coords=np.array([[point_x, point_y]]),
            point_labels=np.array([1]),
            multimask_output=False,
        )

    # Frame 0: encode + predict
    torch.cuda.synchronize() if device == "cuda" else None
    t0 = time.perf_counter()
    with torch.inference_mode():
        predictor.set_image(np.array(frames[0]))
        masks, scores, _ = predictor.predict(
            point_coords=np.array([[point_x, point_y]]),
            point_labels=np.array([1]),
            multimask_output=False,
        )
    torch.cuda.synchronize() if device == "cuda" else None
    t_frame0 = (time.perf_counter() - t0) * 1000
    print(f"  Frame 0 (init): {t_frame0:8.1f} ms  (score={scores[0]:.3f})")

    # Frames 1..N: encode + predict (simulating tracking)
    frame_times = []
    for i in range(1, len(frames)):
        torch.cuda.synchronize() if device == "cuda" else None
        t0 = time.perf_counter()
        with torch.inference_mode():
            predictor.set_image(np.array(frames[i]))
            masks, scores, _ = predictor.predict(
                point_coords=np.array([[point_x, point_y]]),
                point_labels=np.array([1]),
                multimask_output=False,
            )
        torch.cuda.synchronize() if device == "cuda" else None
        dt = (time.perf_counter() - t0) * 1000
        frame_times.append(dt)
        print(f"  Frame {i:2d}:       {dt:8.1f} ms  (score={scores[0]:.3f})")

    avg_track = sum(frame_times) / len(frame_times) if frame_times else 0
    total = t_frame0 + sum(frame_times)

    print(f"\n  --- Summary ---")
    print(f"  Load:           {t_load:8.1f} ms")
    print(f"  Init (frame 0): {t_frame0:8.1f} ms")
    print(f"  Track avg/fr:   {avg_track:8.1f} ms")
    print(f"  Total pipeline: {total:8.1f} ms")

    return {
        "model": model_name,
        "device": device,
        "t_load": t_load,
        "t_frame0": t_frame0,
        "t_track_avg": avg_track,
        "t_total": total,
    }


def main():
    parser = argparse.ArgumentParser(description="SAM2 Python baseline benchmark")
    parser.add_argument("--model", default="tiny", choices=MODEL_CONFIGS.keys())
    parser.add_argument("--video", default="data/test_video.mp4")
    parser.add_argument("--point-x", type=float, default=315.0)
    parser.add_argument("--point-y", type=float, default=250.0)
    parser.add_argument("--n-frames", type=int, default=3)
    parser.add_argument(
        "--cpu",
        action="store_true",
        help="Run on CPU intentionally instead of requiring CUDA",
    )
    args = parser.parse_args()

    if args.cpu:
        device = "cpu"
    else:
        if not torch.cuda.is_available():
            print(
                "ERROR: CUDA is not available. Install a CUDA-enabled PyTorch build "
                "or rerun with --cpu for an explicit CPU comparison.",
                file=sys.stderr,
            )
            sys.exit(1)
        device = "cuda"

    print(f"PyTorch: {torch.__version__}")
    print(f"Device: {device}")
    if device == "cuda":
        print(f"GPU: {torch.cuda.get_device_name(0)}")

    # Decode frames
    print(f"Decoding {args.n_frames} frames from {args.video}...")
    frames, w, h = decode_video_frames(args.video, args.n_frames)
    print(f"  {w}x{h}, {len(frames)} frames")

    # Benchmark
    result = benchmark_sam2_image(
        args.model, frames, args.point_x, args.point_y, device
    )

    # Print comparison table
    print(f"\n{'='*70}")
    print("COMPARISON (copy sam3.cpp numbers from benchmark output):")
    print(f"{'='*70}")
    print(f"  Python SAM2 {args.model} ({device}):  track/fr = {result['t_track_avg']:.1f} ms")
    print(f"  sam3.cpp CUDA:                      track/fr = ??? ms  (run sam3_benchmark)")
    print(f"  sam3.cpp CPU:                       track/fr = ??? ms  (run sam3_benchmark)")


if __name__ == "__main__":
    main()
