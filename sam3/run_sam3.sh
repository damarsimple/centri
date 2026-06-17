#!/usr/bin/env bash
# Supervisor for the SAM3 API server. Coverage degrades over the server's
# lifetime (accumulated GPU/model state), so the server is allowed to recycle
# itself via POST /reset (which exits the process); this loop relaunches a
# fresh one. Also recovers from crashes.
cd /home/damar/sams2/sam3cpp || exit 1
PY=/home/damar/miniconda3/envs/sam3/bin/python
while true; do
    echo "[supervisor $(date '+%H:%M:%S')] starting SAM3 server..."
    "$PY" api_master_sam3.py
    code=$?
    echo "[supervisor $(date '+%H:%M:%S')] SAM3 exited (code=$code); relaunching in 2s..."
    sleep 2
done
