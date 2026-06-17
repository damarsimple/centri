# Change Spec — Phase 0: Expose the Per-Frame Series

> Written **before** implementation so the doc is the spec. Goal: surface the
> already-computed per-frame time-series via the API so the pedagogy backend and the
> accuracy pilot can consume it. Companions: [data-contract.md](data-contract.md),
> [pipeline-internals.md](pipeline-internals.md).

## Goal

Make `GET /result/{job_id}` expose `data/kinematics.csv` (the per-frame series), and
make a her-schema-compatible CSV available for the pedagogy seam + pilot.

## Precondition (why this is small)

- `data/kinematics.csv` is **already written** by Step 8 §5.10 — columns
  `time_s, r_px, r_m, theta_rad, omega_rad_s, v_m_s, ac_m_s2, active`.
- It is **already served statically** at `/files/job_{id}/analysis_output/data/kinematics.csv`
  (`app.mount("/files", StaticFiles(...))`).
- **No pipeline/physics/agent change is required.** Nothing in `orchestrator.txt` or the
  subagents changes. This is pure API plumbing.

## Touchpoints (exact)

### 1. `prompts/job-output-extractor.txt`
- Add `OUTPUT_KINEMATICS_CSV` to the env-override list (currently 4 entries).
- Add to PATH RESOLUTION:
  `kinematics_csv = OUTPUT_KINEMATICS_CSV ?? f"/files/job_{job_id}/analysis_output/data/kinematics.csv"`
- Add a `kinematics_csv` block to the OUTPUT FORMAT `files` object.

### 2. `worker/tasks.py`
- After line ~108, add:
  `extractor_env["OUTPUT_KINEMATICS_CSV"] = "analysis_output/data/kinematics.csv"`
- In `_parse_extractor_output`, add `"kinematics_csv"` to the key tuple (`tasks.py:153`)
  and to the `fallback` dict (`tasks.py:159-164`) with
  `"analysis_output/data/kinematics.csv"`.

### 3. `app/schemas.py`
- Add to `FilePaths`: `kinematics_csv: Optional[str] = None`.
  **Must be `Optional` with a default** — old cached `job:{id}:result` payloads (TTL 48h)
  won't have the key, and required fields would 500 the result endpoint on
  `FilePaths(**result["files"])` (`routes.py:101`).

### 4. (No change) static serving
`/files/...` already serves the file. Nothing to do.

## Her-schema CSV — pick one

Her pedagogy reads `Time (s), Angular velocity (rad/s), Acceleration (m/s^2)`; ours is
`time_s, omega_rad_s, ac_m_s2`. Two options (see [data-contract.md §5](data-contract.md)):

- **(a) Rename at consumption** — the pedagogy backend / pilot notebook renames the three
  columns when it reads our CSV. *Zero change to `agent-backend`.* Recommended for Phase 0
  (keeps this change pure-plumbing); revisit in Phase 1.
- **(b) Emit `data/series.csv`** with her headers from the pipeline. Cleaner single
  artifact for the pilot, but requires an orchestrator (agent-behavior) edit — defer
  unless the pilot wants it.

**Decision for Phase 0:** ship (a). Expose `kinematics.csv` as-is; do the rename
downstream.

## Acceptance criteria

- [ ] A completed job's `/result` returns `files.kinematics_csv` as a `/files/...` URL.
- [ ] That URL serves the CSV with the documented columns and one row per frame.
- [ ] Old/cached results (pre-change) still return `200` (missing key tolerated).
- [ ] `pd.read_csv(url)` + a 3-column rename yields a frame ingestible by a `fastapi-gpt`
      question endpoint (sanity check the seam end-to-end).
- [ ] No change in `stats`, PDFs, video, or panel outputs.

## Out of scope (explicitly)

- Any change to `orchestrator.txt` step logic or subagents.
- Any physics/units change.
- The her-schema emission (option b).

## Follow-ups (note, don't do now)

- **Type `stats.json`.** It's assembled ad-hoc by the agent ([pipeline-internals.md §7](pipeline-internals.md));
  a declared schema would de-risk every consumer.
- **De-hardcode subagent example numbers** (`figures-gen`, `question-gen`) to placeholders.
- **Resolve `cropped.mp4` vs `cropped_iter<N>.mp4`** naming drift.
- **Fix the `../../` extractor URL prefixing** quirk (`REPORT.md §15.1`).
