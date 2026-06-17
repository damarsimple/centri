"""Frozen, deterministic kinematics pipeline (steps 4-8).

This package is *seeded* into every job workspace by the API
(`app/workspace.py::seed_pipeline`) — exactly like `sidecar.json` and the
template video. The orchestrator agent (pi) does NOT author this code; it only
runs `python -m analysis.run` after it has finished perception/tracking.

Why it exists: when the agent re-authored this math each run we observed 28
distinct `stats.json` schemas across 30 jobs, bare `NaN` in 17 of them, and
`center_drift_px` swinging 8.9->1013 on the *same* video. Freezing the math here
makes "same inputs -> identical stats.json" true by construction.

See README.md for the input contract and the locked stats.json schema.
"""

__all__ = ["contract", "geometry", "kinematics", "writer", "run", "common"]
