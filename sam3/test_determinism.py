import requests
import json
import numpy as np
import os

def call_api(video_path, targets):
    api_url = "http://localhost:8086/track"
    with open(video_path, 'rb') as f:
        files = {'file': (os.path.basename(video_path), f, 'video/quicktime')}
        data = {'targets': json.dumps(targets)}
        response = requests.post(api_url, files=files, data=data)
    return response.json()

def compare_tracks(files):
    tracks = []
    for f in files:
        with open(f, 'r') as j:
            tracks.append(json.load(j)['trajectories']['red phone'])
    
    # Check lengths
    lengths = [len(t) for t in tracks]
    print(f"Track lengths: {lengths}")
    if len(set(lengths)) > 1:
        print("Warning: Track lengths differ!")
    
    min_len = min(lengths)
    
    diffs = []
    for i in range(min_len):
        coords = np.array([[t[i]['cx'], t[i]['cy']] for t in tracks])
        # Calculate max distance between any two versions at this frame
        max_diff = 0
        for j in range(len(tracks)):
            for k in range(j + 1, len(tracks)):
                d = np.linalg.norm(coords[j] - coords[k])
                max_diff = max(max_diff, d)
        diffs.append(max_diff)
    
    max_total_diff = max(diffs)
    avg_total_diff = sum(diffs) / len(diffs)
    
    print(f"Max coordinate difference across runs: {max_total_diff:.10f} pixels")
    print(f"Average coordinate difference: {avg_total_diff:.10f} pixels")
    
    return max_total_diff

def main():
    video_path = "/home/damar/sams2/sam3cpp/IMG_3075.MOV"
    targets = ["red phone"]
    
    print("Running Run 2...")
    res2 = call_api(video_path, targets)
    with open("red_phone_track_2.json", "w") as f:
        json.dump(res2, f)
        
    print("Running Run 3...")
    res3 = call_api(video_path, targets)
    with open("red_phone_track_3.json", "w") as f:
        json.dump(res3, f)
    
    print("\nComparing Results...")
    files = ["red_phone_track.json", "red_phone_track_2.json", "red_phone_track_3.json"]
    compare_tracks(files)

if __name__ == "__main__":
    main()
