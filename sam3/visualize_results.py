import cv2
import json
import numpy as np
import os
import sys

def visualize(video_path, json_path, output_path):
    print(f"Opening video: {video_path}")
    print(f"Opening JSON: {json_path}")
    
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    if data['status'] != 'success':
        print("JSON status is not success")
        return

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Error: Could not open video {video_path}")
        return

    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0: fps = 60.0
    
    print(f"Video resolution: {w}x{h} @ {fps}fps")

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (w, h))

    trajectories = data['trajectories']
    
    # Exaggerated Colors
    target_colors = {
        "red smartphone": (0, 0, 255),      # Bright Red
        "red phone": (0, 0, 255),           # Bright Red
        "rear bicycle tire": (255, 0, 0),   # Bright Blue
        "pedal": (0, 255, 0),               # Neon Green
    }
    default_colors = [
        (0, 255, 255), (255, 0, 255), (255, 255, 0), (255, 128, 0), (0, 128, 255)
    ]

    # Map frame index to data
    frame_map = {}
    history = {name: [] for name in trajectories.keys()}
    
    for target_name, frames in trajectories.items():
        for f in frames:
            f_idx = f['frame']
            if f_idx not in frame_map:
                frame_map[f_idx] = []
            frame_map[f_idx].append((target_name, f))

    all_frames = sorted(frame_map.keys())
    if not all_frames:
        print("No frames found")
        return
    
    start_f = all_frames[0]
    end_f = all_frames[-1]
    
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_f)
    
    for f_idx in range(start_f, end_f + 1):
        ret, frame = cap.read()
        if not ret: break
        
        if f_idx in frame_map:
            for i, (name, f_data) in enumerate(frame_map[f_idx]):
                color = target_colors.get(name, default_colors[i % len(default_colors)])
                
                # Update history for trail
                history[name].append((int(f_data['cx']), int(f_data['cy'])))
                if len(history[name]) > 60: # Keep 1 second of trail
                    history[name].pop(0)
                
                # Draw Trail (Exaggerated)
                if len(history[name]) > 1:
                    for j in range(1, len(history[name])):
                        thickness = int(np.sqrt(10 * float(j) / len(history[name])) * 2) + 1
                        cv2.line(frame, history[name][j-1], history[name][j], color, thickness)

                # Draw OBOX (Thicker)
                if 'obox' in f_data:
                    pts = np.array(f_data['obox'], np.int32)
                    cv2.polylines(frame, [pts], True, color, 6) # Thick lines
                elif 'bbox' in f_data:
                    b = f_data['bbox']
                    cv2.rectangle(frame, (int(b[0]), int(b[1])), (int(b[2]), int(b[3])), color, 6)
                
                # Draw center (Larger)
                cx, cy = int(f_data['cx']), int(f_data['cy'])
                cv2.circle(frame, (cx, cy), 12, color, -1)
                cv2.circle(frame, (cx, cy), 15, (255, 255, 255), 2) # White outline
                
                # Draw Label (Larger and with background)
                label = f"{name.upper()}"
                (lw, lh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_DUPLEX, 1.2, 2)
                cv2.rectangle(frame, (cx + 15, cy - lh - 10), (cx + 15 + lw + 10, cy + 10), (0,0,0), -1)
                cv2.putText(frame, label, (cx + 20, cy), cv2.FONT_HERSHEY_DUPLEX, 1.2, color, 2)
        
        out.write(frame)
        if f_idx % 50 == 0:
            print(f"Rendered frame {f_idx}")

    cap.release()
    out.release()
    print(f"Visualization saved to: {output_path}")

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python3 visualize_results.py <video> <json> <output>")
    else:
        visualize(sys.argv[1], sys.argv[2], sys.argv[3])
