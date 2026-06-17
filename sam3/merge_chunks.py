import json

merged = {"status": "success", "trajectories": {}}

for i in range(3):
    with open(f"chunk{i}.json", "r") as f:
        data = json.load(f)
        for label, traj in data.get("trajectories", {}).items():
            if label not in merged["trajectories"]:
                merged["trajectories"][label] = []
            merged["trajectories"][label].extend(traj)

# Sort
for label in merged["trajectories"]:
    merged["trajectories"][label].sort(key=lambda x: x["frame"])

with open("results_parallel.json", "w") as f:
    json.dump(merged, f)
