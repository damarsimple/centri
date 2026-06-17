# agent-backend docs

Deep-dive documentation for the circular-motion measurement backend and how it fits
the broader system. `REPORT.md` (repo root) remains the ops/deploy reference; these
docs cover internals, the cross-system plan, and pending changes.

| Doc | What it covers |
|---|---|
| [improvement-changelog.md](improvement-changelog.md) | **Start-to-finish story of the determinism overhaul** — the symptom, root cause, what changed file-by-file, the bug the spot-check caught, and before/after results. Read this for "what changed and why". |
| [validation-report.md](validation-report.md) | The live before/after numbers: determinism + gyro accuracy across the 3× per-video re-run. |
| [agents-behaviour.md](agents-behaviour.md) | **All five agents** + the frozen pipeline: model, I/O, and which layers are LLM-driven vs deterministic. Start here for "what does each agent do". |
| [pipeline-internals.md](pipeline-internals.md) | The `pi` agent's 6-step behavior, the frozen kinematics pipeline, algorithms, coordinate spaces, validation flags. Read before changing agent behavior. |
| [data-contract.md](data-contract.md) | Every data shape in/out: sidecar, tracking API, `pipeline_inputs.json`, `kinematics.csv`, `stats.json` (locked schema), `/result` — and the **seam** to the `fastapi-gpt` pedagogy. |
| [subagents.md](subagents.md) | The `pi` subagents (video annotation, figures, question-gen, latex), the harness/model, and agent-behavior caveats. |
| [../workspace_lib/analysis/README.md](../workspace_lib/analysis/README.md) | The frozen, seeded kinematics pipeline: input contract, locked output schema, determinism guarantees. |
| [architecture-overview.md](architecture-overview.md) | Cross-system: the three systems, ownership, deployment topology, modality-substitution plan, phase roadmap, accuracy pilot. |
| [change-spec-phase0.md](change-spec-phase0.md) | Exact spec for exposing the per-frame series via the API (pure plumbing; no pipeline change). |
| [tunneling.md](tunneling.md) | (existing) socat reverse-proxy tunnel setup. |

**Start here:** new to the system → `architecture-overview.md`; changing the pipeline →
`pipeline-internals.md`; wiring video into pedagogy or the pilot → `data-contract.md`.
