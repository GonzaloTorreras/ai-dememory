# ADR 0055: Maintenance Artifact Status

Status: Accepted for the v2 draft.

## Context

Maintenance now refreshes generated index, graph, weight, lifecycle score, and
lifecycle report artifacts. `ai-dememory maintenance status` and MCP
`memory.maintenance_status` reported schedules, providers, recent reports, and
lock state, but not whether the generated artifacts existed or when they were
last refreshed.

Schedulers and local MCP clients need a quick read-only way to explain whether
daily or weekly maintenance has actually produced the expected performance and
quality artifacts.

## Decision

Add an `artifacts` object to maintenance status. It reports the generated
artifact path, existence, update timestamp, and size for:

- `indexes/memory.sqlite`
- `indexes/memory-graph.json`
- `indexes/memory-weights.json`
- `indexes/memory-lifecycle.json`
- `reports/lifecycle.md`

The status command remains read-only. It does not rebuild artifacts, run
maintenance, install scheduler state, or mutate canonical memory.

## Benefits

- Lets users and MCP clients diagnose stale or missing maintenance outputs.
- Makes scheduled maintenance easier to verify without opening generated files.
- Complements ADR 0054 by exposing the lifecycle artifacts it now refreshes.

## Limitations

- Timestamps are local filesystem modification times, not signed provenance.
- The status does not inspect artifact contents for semantic correctness.
- It does not decide whether artifacts should be committed; artifact guard still
  treats them as generated disposable outputs.

## Future Risks

- Additional generated artifacts may need to be added to the status map as v2
  grows.
- Filesystem timestamp resolution can vary by platform, which may matter for
  future freshness thresholds.

## Dependencies

- ADR 0020 defines generated artifact staging boundaries.
- ADR 0054 defines lifecycle artifacts refreshed by maintenance.
- `scripts/maintenance.py` remains the source for maintenance status.
