import sys
import os
import argparse
import json
import torch
import cv2
import numpy as np
import gc
from ultralytics import YOLOWorld
from sam2.build_sam import build_sam2_video_predictor

# ──────────────────────────────────────────────────────────
# Windowed propagation config
# Tune WINDOW_SIZE down if you still hit OOM (e.g. 100).
WINDOW_SIZE = 600   # frames processed per SAM2 init_state call
OVERLAP     = 10    # frames re-processed for smooth hand-off between windows
# ──────────────────────────────────────────────────────────


def sorted_frame_paths(video_dir: str) -> list[str]:
    """Return absolute paths of all .jpg frames, sorted numerically."""
    frames = sorted(
        [f for f in os.listdir(video_dir) if f.endswith(".jpg")],
        key=lambda x: int(os.path.splitext(x)[0])
    )
    return [os.path.join(video_dir, f) for f in frames]


def bbox_from_mask(mask: np.ndarray) -> np.ndarray | None:
    """Convert a binary mask to [x1, y1, x2, y2] bbox, or None if empty."""
    coords = np.where(mask)
    if len(coords[0]) == 0:
        return None
    y1, y2 = int(coords[0].min()), int(coords[0].max())
    x1, x2 = int(coords[1].min()), int(coords[1].max())
    return np.array([x1, y1, x2, y2], dtype=np.float32)


def process_window(
    predictor,
    window_paths: list[str],
    window_dir: str,
    prompts: dict,          # obj_id -> {'box': np.ndarray}
    id_to_label: dict,
    device,
) -> dict:
    """
    Run SAM2 on one window.
    `window_dir` is a temp symlink/copy directory listing only this window's frames.
    Returns dict: obj_id -> list of {'frame_abs': int, 'cx', 'cy', 'bbox': [x1,y1,x2,y2]}
    """
    # Build a temp directory with symlinks named 00000.jpg … for this window
    os.makedirs(window_dir, exist_ok=True)
    for local_idx, abs_path in enumerate(window_paths):
        link = os.path.join(window_dir, f"{local_idx:05d}.jpg")
        if os.path.exists(link) or os.path.islink(link):
            os.remove(link)
        os.symlink(abs_path, link)

    window_results = {obj_id: [] for obj_id in prompts}

    with torch.cuda.device(device):
        with torch.amp.autocast(device_type="cuda", dtype=torch.bfloat16):
            inference_state = predictor.init_state(video_path=window_dir)

            for obj_id, prompt in prompts.items():
                box_np = prompt["box"]
                box_tensor = torch.from_numpy(box_np).to(device=device, dtype=torch.bfloat16)
                predictor.add_new_points_or_box(
                    inference_state=inference_state,
                    frame_idx=0,
                    obj_id=obj_id,
                    box=box_tensor,
                )

            for local_frame_idx, out_obj_ids, out_mask_logits in predictor.propagate_in_video(inference_state):
                for i, obj_id in enumerate(out_obj_ids):
                    mask = (out_mask_logits[i] > 0.0).cpu().numpy()[0]
                    coords = np.where(mask)
                    bbox = bbox_from_mask(mask)
                    if len(coords[0]) > 0:
                        entry = {
                            "local_frame": local_frame_idx,
                            "cx": float(np.mean(coords[1])),
                            "cy": float(np.mean(coords[0])),
                            "bbox": bbox.tolist() if bbox is not None else None,
                        }
                    else:
                        entry = {"local_frame": local_frame_idx, "cx": -1, "cy": -1, "bbox": None}
                    window_results[obj_id].append(entry)

            predictor.reset_state(inference_state)

    # Cleanup symlinks
    for f in os.listdir(window_dir):
        os.remove(os.path.join(window_dir, f))
    os.rmdir(window_dir)

    gc.collect()
    torch.cuda.empty_cache()

    return window_results


def run_worker(video_dir: str, target_list: list[str], output_json: str):
    print(f">>> WORKER STARTING: Targets {target_list} <<<", flush=True)
    device = torch.device("cuda")

    # ── 1. YOLO-World grounding on frame 0 ────────────────
    print("Loading YOLO-World...", flush=True)
    yolo_model = YOLOWorld("yolov8l-worldv2.pt")
    yolo_model.set_classes(target_list)

    frame_0_path = os.path.join(video_dir, "00000.jpg")
    results = yolo_model.predict(frame_0_path, conf=0.1, verbose=False)

    target_boxes: dict[str, dict] = {}
    for box in results[0].boxes:
        cls_id = int(box.cls[0])
        label = target_list[cls_id]
        coords = box.xyxy[0].cpu().numpy()
        if label not in target_boxes or float(box.conf[0]) > target_boxes[label]["conf"]:
            target_boxes[label] = {"box": coords, "conf": float(box.conf[0])}

    if not target_boxes:
        print("ERROR: No targets found in Frame 0", flush=True)
        sys.exit(1)

    # Free YOLO VRAM before loading SAM2
    del yolo_model
    gc.collect()
    torch.cuda.empty_cache()

    # ── 2. Build SAM2 predictor (loaded once, reused per window) ──
    print("Building SAM 2.1 Predictor...", flush=True)
    checkpoint = "/home/damar/sams2/segment-anything-2/checkpoints/sam2.1_hiera_large.pt"
    config = "configs/sam2.1/sam2.1_hiera_l.yaml"
    predictor = build_sam2_video_predictor(config, checkpoint, device=device)

    # ── 3. Build obj_id ↔ label maps ──────────────────────
    label_to_id: dict[str, int] = {label: i + 1 for i, label in enumerate(target_boxes)}
    id_to_label: dict[int, str] = {v: k for k, v in label_to_id.items()}

    # Initial prompts from YOLO detections
    current_prompts: dict[int, dict] = {
        obj_id: {"box": target_boxes[label]["box"]}
        for label, obj_id in label_to_id.items()
    }

    # ── 4. Windowed propagation ────────────────────────────
    all_frame_paths = sorted_frame_paths(video_dir)
    total_frames = len(all_frame_paths)
    print(f"Total frames: {total_frames}. Window={WINDOW_SIZE}, Overlap={OVERLAP}", flush=True)

    # Accumulate per-label results indexed by absolute frame number
    final_results: dict[str, dict[int, dict]] = {label: {} for label in target_boxes}

    window_start = 0
    window_idx = 0
    tmp_base = os.path.join(os.path.dirname(video_dir), "_window_tmp")

    while window_start < total_frames:
        window_end = min(window_start + WINDOW_SIZE, total_frames)
        window_paths = all_frame_paths[window_start:window_end]
        window_dir_path = os.path.join(tmp_base, f"win_{window_idx:04d}")

        print(f"  Window {window_idx}: frames [{window_start}, {window_end}) "
              f"({len(window_paths)} frames)", flush=True)

        window_results = process_window(
            predictor=predictor,
            window_paths=window_paths,
            window_dir=window_dir_path,
            prompts=current_prompts,
            id_to_label=id_to_label,
            device=device,
        )

        # Map local frame indices → absolute frame indices
        # Overlap frames from the *previous* window are already stored; skip re-writing
        # We overwrite the overlap region with the newer (fresher) propagation result.
        for obj_id, entries in window_results.items():
            label = id_to_label[obj_id]
            last_valid_bbox = None
            for entry in entries:
                abs_frame = window_start + entry["local_frame"]
                final_results[label][abs_frame] = {
                    "frame": abs_frame,
                    "cx": entry["cx"],
                    "cy": entry["cy"],
                }
                if entry["bbox"] is not None:
                    last_valid_bbox = np.array(entry["bbox"], dtype=np.float32)

            # Update prompt for the next window using last valid bbox in this window
            if last_valid_bbox is not None:
                current_prompts[obj_id] = {"box": last_valid_bbox}
            # else: keep existing prompt (object was lost in this window)

        # Advance; next window starts at (window_end - OVERLAP) to re-process overlap
        if window_end >= total_frames:
            break
        window_start = window_end - OVERLAP
        window_idx += 1

    # Cleanup tmp base if empty
    try:
        os.rmdir(tmp_base)
    except OSError:
        pass

    # ── 5. Flatten and sort results ───────────────────────
    trajectories: dict[str, list] = {}
    for label, frame_dict in final_results.items():
        trajectories[label] = [v for _, v in sorted(frame_dict.items())]

    output_data = {
        "status": "success",
        "detections": {k: v["conf"] for k, v in target_boxes.items()},
        "trajectories": trajectories,
    }

    with open(output_json, "w") as f:
        json.dump(output_data, f)

    print(f">>> WORKER FINISHED. Results saved to {output_json} <<<", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--video_dir", required=True)
    parser.add_argument("--targets", required=True)  # JSON string
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    targets = json.loads(args.targets)
    run_worker(args.video_dir, targets, args.output)
