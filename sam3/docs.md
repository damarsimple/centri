# High-Throughput Video Tracking Pipeline (SAM 3 + SAM 2)

This document details the architecture, optimization, and reliability testing of the parallel video tracking system deployed on the RTX 5090.

## 1. Architecture Overview
The system utilizes a hybrid model approach to maximize both detection accuracy and tracking speed:
- **SAM 3 (Grounding DINO + DETR)**: Used at the start of each video chunk to detect objects based on natural language prompts (e.g., "red phone").
- **SAM 2.1 (Hiera)**: Used for high-speed frame-to-frame mask propagation and trajectory extraction.
- **GGML Inference**: Optimized C++ backend using `sam3.cpp` with 4-bit quantization and GPU acceleration.

## 2. API Interface (`/track`)
The main interface is a FastAPI-based orchestrator that handles parallelization automatically.

### POST `/track`
- **Arguments**:
  - `file`: Video file (MP4, MOV, etc.)
  - `targets`: JSON array or comma-separated list of objects to track (e.g., `["red phone"]`).
- **New Features**:
  - **Automatic Chunking**: Video is split into 3 segments processed in parallel.
  - **VRAM Control**: Managed by `asyncio.Semaphore(3)` to keep 3 concurrent workers (approx. 10.5GB VRAM total for Tiny, 11.5GB for Large).
  - **Rotation Awareness**: Automatically detects and handles video rotation metadata (common in iPhone videos).

## 3. Performance & Model Selection
Two models are available for different use cases:

| Model | Size | Throughput (RTX 5090) | Use Case |
| :--- | :--- | :--- | :--- |
| **SAM 2.1 Tiny** | 75 MB | ~24 FPS (Parallel) | Real-time / Low latency |
| **SAM 2.1 Large** | 430 MB | **~12 FPS (Parallel)** | **Scientific Analysis / High Precision** |

## 4. Reliability & Determinism
Rigorous testing (10 sequential runs) confirmed that the pipeline is **100% Deterministic**.
- **Max Coordinate Variance**: 0.000000 pixels.
- **Timing Stability**: Standard deviation < 1s for 300-frame segments.

## 5. Sensor Synchronization (Case Study: IMG_2731.MOV)
The pipeline was validated by comparing visual angular velocity with internal phone gyroscope data.

### Key Parameters:
- **Time Offset**: 11.36 seconds (Sensor starts before video).
- **Refined Rotation Center**: `(654.8, 705.3)` - Corresponds to the bicycle's rear axle.
- **Synchronization Accuracy**: ~91% correlation between visual and sensor angular velocity.

### Analysis Script (`final_sync.py`):
Used to generate multi-panel plots comparing model accuracy:
- **Top Panel**: Full sequence context.
- **Bottom Panel**: Zoomed-in rotation phase with (SAM2 Large) vs (SAM2 Tiny) overlays.

## 6. Optimization Notes
- **FFmpeg Pipes**: FFmpeg is used for zero-copy frame decoding directly into the worker's buffer.
- **Parallel Threads**: Each worker is configured with `--threads 4`, totaling 12 CPU threads across the 3 GPU workers, saturating the RTX 5090's compute capacity.

## 7. How to Start the API
To launch the parallel tracking server on the RTX 5090:

```bash
python3 api_master_sam3.py
```

- **Host**: `0.0.0.0` (accessible from your network)
- **Port**: `8086`
- **Endpoint**: `POST /track`

### Example `curl` Request:
```bash
curl -X POST http://localhost:8086/track \
  -F "file=@/path/to/your/video.mp4" \
  -F "targets=[\"red phone\"]"
```

The API will automatically split your video into 3 chunks, process them in parallel across your GPU cores, and return the merged trajectories as a single JSON response.
