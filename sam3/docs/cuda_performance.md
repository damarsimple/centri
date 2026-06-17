# CUDA Performance Optimization Log

Tracking document for all CUDA optimizations attempted on sam3.cpp.
GPU: NVIDIA GeForce RTX 4080 (16GB VRAM, compute capability 8.9, Ada Lovelace).

## Baseline

- **Build**: `cmake .. -DSAM3_CUDA=ON && make -j$(nproc)`
- **Profile**: `SAM3_PROFILE=1 ./build-cuda/examples/sam3_benchmark --filter <model> --n-frames 5`
- **Test**: `./build-cuda/examples/sam3_benchmark --filter <model> --n-frames 5` (all runs must report OK, Det counts must match CPU)

## Current Best Results (SAM3, RTX 4080)

| Model | Size | CPU (ms/fr) | CUDA (ms/fr) | Speedup | FPS |
|-------|------|-------------|--------------|---------|-----|
| SAM3 f16 | 1.7 GB | 33,844 | **~1,100** | **~31x** | ~0.9 |
| SAM3 q4_0 | 673 MB | 38,774 | **1,030** | **37.6x** | ~1.0 |
| SAM2.1 tiny f16 | 75 MB | 3,915 | **118** | **33.2x** | **~8.5** |
| SAM2.1 tiny q8_0 | 40 MB | 3,767 | **111** | **33.9x** | **~9.0** |
| SAM2.1 tiny q4_0 | 22 MB | 4,159 | **125** | **33.3x** | **~8.0** |

## Optimizations Applied

### 1. CUDA Backend Support (commit e4abacb)

**What**: Added `SAM3_CUDA` CMake option. Backend init chain: CUDA → Metal → CPU.

**Result**: First working CUDA run. Image encode: 716ms CUDA vs 2996ms CPU (4.2x).

### 2. Flash Attention SDPA Fallback (commit 9f6f0ef)

**What**: CUDA flash attention only supports head dims in {40,64,72,80,96,112,128,256,576}. The SAM decoder, geometry encoder, fusion encoder, and DETR decoder all use D=256 with 8 heads = HD=32, which is unsupported. Added `sam3_flash_attn_or_sdpa()` wrapper that falls back to manual Q*K^T → scale → softmax → V.

**Why needed**: Without this, any sub-graph using HD=32 attention crashes with `GGML_ABORT("fatal error")` in `fattn.cu:492`.

**Affected paths**: SAM decoder (PVS/PCS), geometry encoder, fusion encoder (6 layers), DETR decoder (6 layers), SAM two-way attention blocks.

**Not affected**: ViT backbone (HD=64), text encoder (HD=64), Hiera blocks (HD=96), memory attention (HD=256, single head), perceiver (HD=256, single head).

**Result**: All 3 quantizations of SAM2.1 tiny pass. ~6x speedup over CPU.

**Future**: When ggml adds HD=32 support to CUDA FA kernels, the wrapper will automatically use FA (it checks HD at graph build time).

### 3. Device-to-Device Tensor Copy (commit ee0ea06)

**What**: Replaced `ggml_backend_tensor_get` + `ggml_backend_tensor_set` patterns with `ggml_backend_tensor_copy` where both source and destination are backend tensors with matching layouts. On CUDA this uses `cudaMemcpyDeviceToDevice` (~microseconds) instead of GPU→CPU→GPU via PCIe (~hundreds of ms).

**Optimized paths**:
- FPN outputs → state.neck_trk (4 call sites across all encoder functions)
- state.neck_trk[0,1] → graph inputs in segment_pvs (feat_s0, feat_s1)
- state.neck_trk[0,1] → graph inputs in propagate_single (trk_s0, trk_s1)
- state.neck_trk[2] → pix_in_raw in encode_memory

**Not optimized (layout mismatch)**:
- `state.neck_trk[2]` [D,H,H,1] (4D) → `curr` [D,N,1] (3D) in propagate_single — requires reshape, still goes through CPU.

**Not optimized (CPU processing required)**:
- `neck_trk[2]` + `no_mem_embed` addition in segment_pvs — CPU adds the bias before upload
- Image pixel upload — data originates on CPU
- Mask/IoU readback — CPU needs results for post-processing

**Result (SAM2.1 tiny f16, RTX 4080, 5 frames)**:
| Metric | Before | After | Change |
|--------|--------|-------|--------|
| CUDA track/frame | 748ms | 672ms | -10% |
| SAM decode (segment_pvs) | 120ms | 69ms | -42% |
| CPU track/frame | 4795ms | 4627ms | -3.5% (no regression) |

### 4. Window Partition via Reshape+Permute (commit c78709a)

**What**: The SAM3 ViT uses `ggml_win_part`/`ggml_win_unpart` for window attention. The CUDA backend has no kernel for these ops. Replaced with reshape+permute sequences (same approach already used by SAM2 Hiera).

**Why needed**: Without this, SAM3 crashes on CUDA with `op not supported node_17 (WIN_PART)`.

**Result**: SAM3 runs on CUDA — 28.5x speedup over CPU (1258ms vs 35868ms per frame).

**Verification**: CPU produces identical Det=1 before and after the change (reshape+permute is mathematically equivalent to win_part).

## Profiling Breakdown (SAM2.1 tiny f16, CUDA, after all optimizations)

### Image Encode (frame 0, includes first-time setup)
| Section | Time | % |
|---------|------|---|
| preprocess (CPU resize+normalize) | 19ms | 1.5% |
| graph_alloc | 0.4ms | 0% |
| data_upload (image pixels CPU→GPU) | 239ms | 18.6% |
| backbone_compute (GPU) | 80ms (first) / 23ms (cached) | 6% |
| data_readback (PE setup + state copy) | 302ms | 23.5% |
| total | 642ms | |

### Tracking (per frame, steady state)
| Section | Time | % |
|---------|------|---|
| encode_image | 582ms | ~87% |
| propagate_single | ~85ms | ~13% |
| total | ~672ms | |

### 5. Cache Hiera Positional Embedding (commit d02b3d5)

**What**: The Hiera positional embedding computation (bicubic interpolation of background PE + window PE tiling) depends only on model weights and img_size, both constant during tracking. Cache the result with invalidation on img_size change.

**Result**: SAM2.1 tiny f16 CUDA: 264ms → 118ms/frame (-55%). The bicubic interpolation was ~240ms per frame — far more than the backbone compute itself.

**Bug fix (commit a6f2305)**: The SAM2 encoder was freeing pe_buf every frame, defeating the sinusoidal PE cache. Removing the free dropped SAM2 from 264ms to 118ms.

### 6. Cache Sinusoidal PE Across Frames (commit 31bc5f4)

**What**: Sinusoidal position embeddings depend only on spatial dims + neck_dim (constant per model). Cached the 4-level PE buffer across frames instead of recomputing + reuploading each time.

**Data volume eliminated per frame**: ~28M floats (~112MB) across 4 FPN scales (288², 144², 72², 36²).

**Result**: SAM3 f16 CUDA: 1258ms → 1058ms/frame (-15.9%).

## Profiling Breakdown (SAM3 f16, CUDA, after all optimizations)

### Image Encode (per frame, steady state)
| Section | Time | Notes |
|---------|------|-------|
| preprocess | 18ms | CPU resize + normalize |
| graph_alloc | 0.7ms | Negligible |
| data_upload | 0.8ms | Image already on GPU |
| backbone_compute (ViT) | 956ms | 32-block ViT dominates |
| data_readback (first frame) | 200ms | PE setup (cached after) |
| data_readback (subsequent) | ~1ms | PE already cached |
| total (first) | ~1260ms | |
| total (subsequent) | ~1060ms | |

### Tracking (per frame)
| Section | Time | Notes |
|---------|------|-------|
| encode_image | ~1060ms | 85% of frame time |
| detection + tracking | ~80ms | PCS/PVS + propagate |
| total | ~1060ms | |

**Key insight for SAM3**: The ViT backbone (32 blocks, 1024-dim, 72×72 tokens) dominates at ~950ms. Data transfer overhead is minimal. Further speedups require ViT-level optimization (CUDA graphs, kernel fusion).

**Key insight for SAM2.1 tiny**: After all caching optimizations, data transfer is <5ms. The 118ms/frame is split roughly: 43ms encode (23ms GPU compute + 15ms CPU preprocess) + 75ms propagate (memory attention + SAM decode). Near the practical limit for this architecture on RTX 4080.

## Remaining Optimization Opportunities

### High Impact

1. **Pinned host memory for image upload** — `data_upload` is 239ms. Using `ggml_backend_cuda_host_buffer_type()` for CPU-side image buffers enables DMA transfers which are 2-3x faster than pageable memcpy.

2. **Eliminate curr tensor CPU roundtrip** — The `propagate_single` function copies `neck_trk[2]` [D,H,H,1] → `curr` [D,N,1] through CPU because of a 4D→3D layout mismatch. Fix: create `curr` as 4D [D,H,H,1] matching neck_trk[2], then reshape inside the graph.

3. **Keep PE computation on GPU** — The sinusoidal position embeddings are computed on CPU then uploaded. Could be computed as a ggml graph on the GPU.

### Medium Impact

4. **CUDA graphs** — ggml supports `GGML_CUDA_GRAPHS`. For repeated pipeline patterns (tracking frames 1..N all run the same graph structure), CUDA graphs can batch kernel launches and reduce CPU-side overhead.

5. **Async transfers** — Overlap image preprocessing with previous frame's GPU compute using `ggml_backend_tensor_copy_async`.

6. **Fuse sub-graphs** — The graph isolation requirement (CLAUDE.md) forces separate allocations per stage. Could explore a persistent output buffer scheme to reduce per-frame allocation overhead.

### Low Impact / Speculative

7. **cuBLAS workspace tuning** — `GGML_CUDA_FORCE_MMQ` vs default cuBLAS for the matmul-heavy backbone.

8. **FP16 accumulation** — Some operations could use FP16 accumulators for speed at the cost of precision.

9. **Quantization-specific kernels** — q4_0 and q8_0 show similar CUDA perf to f16 (GPU compute is not the bottleneck). Once data transfer is optimized, quantization differences will become visible.

## What NOT to Try

- **Multi-GPU split** — Single model fits in 16GB. Multi-GPU adds latency from cross-device sync.
- **TensorRT/cuDNN** — ggml has its own kernel implementations. Swapping backends is a different project.
- **Graph merging across pipeline stages** — Violates the ggml graph allocator isolation rule (produces silently wrong results, not crashes).

## How to Profile

```bash
# Full profile with table output:
SAM3_PROFILE=1 ./build-cuda/examples/sam3_benchmark --filter tiny_f16 --n-frames 3 --gpu-only

# Quick iteration (rebuild + test):
./scripts/cuda_test.sh --quick

# Autotune sweep:
./scripts/cuda_autotune.sh --quick

# NVIDIA system profiler (kernel-level):
nsys profile --stats=true ./build-cuda/examples/sam3_benchmark --filter tiny_f16 --n-frames 2 --gpu-only

# NVIDIA compute profiler (single kernel):
ncu --set full ./build-cuda/examples/sam3_benchmark --filter tiny_f16 --n-frames 2 --gpu-only
```
