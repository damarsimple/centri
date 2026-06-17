import cv2
import json
import os

def sample_frames(video_path, json_path, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    cap = cv2.VideoCapture(video_path)
    
    # Get rotation robustly
    rotation = 0
    try:
        import subprocess
        probe_cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", video_path]
        probe_data = json.loads(subprocess.check_output(probe_cmd).decode())
        for stream in probe_data.get('streams', []):
            if 'side_data_list' in stream:
                for sd in stream['side_data_list']:
                    if 'rotation' in sd:
                        rotation = int(sd['rotation'])
                        break
    except: pass

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    trajectories = data.get('trajectories', {})
    
    def rotate_point(x, y, rotation, W, H):
        if rotation == -90 or rotation == 270: return int(W - y), int(x)
        if rotation == 90 or rotation == -270: return int(y), int(H - x)
        if rotation == 180 or rotation == -180: return int(H - x), int(W - y)
        return int(x), int(y)

    for sec in range(int(total_frames / fps) + 1):
        frame_idx = int(sec * fps)
        if frame_idx >= total_frames: break
        
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret: break
        
        # Draw boxes
        for label, traj in trajectories.items():
            det = next((d for d in traj if d['frame'] == frame_idx), None)
            if det:
                bbox_L = det['bbox']
                p1 = rotate_point(bbox_L[0], bbox_L[1], rotation, w, h)
                p2 = rotate_point(bbox_L[2], bbox_L[3], rotation, w, h)
                x0, y0 = min(p1[0], p2[0]), min(p1[1], p2[1])
                x1, y1 = max(p1[0], p2[0]), max(p1[1], p2[1])
                
                cv2.rectangle(frame, (x0, y0), (x1, y1), (0, 255, 0), 3)
                cv2.putText(frame, f"{label} f{frame_idx}", (x0, y0-10), 
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        
        out_path = os.path.join(output_dir, f"sample_sec_{sec:02d}_f{frame_idx}.jpg")
        cv2.imwrite(out_path, frame)
        print(f"Saved {out_path}")

    cap.release()

if __name__ == "__main__":
    sample_frames("IMG_2539.MOV", "results_parallel.json", "debug_samples")
