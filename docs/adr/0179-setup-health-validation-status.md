# ADR 0179: Setup Health Validation Status

Status: Accepted

## Context

ADR 0153 made setup health the read-only local status surface for first-run and
maintenance setup. It already combines scheduler, provider, maintenance,
generated artifact, hook, false-positive, and conflict review state. ADR 0177
added structured `validate --json` output, and ADR 0178 exposed the same status
over MCP as `memory.validate_status`.

Users and MCP setup flows still had to call a separate validation command to
know whether the vault was schema-valid before indexing or enabling schedules.

## Decision

Add `validation_status` to `ai-dememory setup health --json` and MCP
`memory.setup_health`. The field reuses the structured validation result from
`validate_repo_result`, including `ok`, `exit_code`, `memory_count`, `messages`,
`errors`, and `conflict_review`.

Setup health remains read-only. It does not write reports, review state,
indexes, schedules, hooks, provider imports, or canonical memory. The top-level
`ready` flag now requires validation to pass in addition to scheduler
environment readiness and persisted schedule validity. When validation fails,
`next_actions` points reviewers to `ai-dememory validate --json`.

## Benefits

- First-run setup gets one passive health response that includes validation
  readiness.
- MCP clients can decide whether indexing or scheduler setup is premature
  without shelling out separately.
- Validation behavior stays shared with the CLI and `memory.validate_status`.
- Runtime smoke now protects the setup-health validation field.

## Limitations

- The field includes validation summaries and conflict counts, not full
  conflict objects.
- Active conflicts remain non-blocking unless validation policy changes later.
- Setup health may perform the same validation work as callers that also invoke
  `memory.validate_status` separately.

## Future Risks

- If validation becomes severity-aware, setup-health `ready` may become false
  for conflict categories that are currently warnings.
- If setup health grows client-specific rendering, it must keep the raw
  `validation_status` object stable for automation.

## Dependencies

- ADR 0153 defines setup health as the passive local setup status surface.
- ADR 0177 defines the structured validation payload.
- ADR 0178 exposes validation status through MCP.
- `scripts/setup_plan.py` owns setup-health assembly.
- `scripts/validate_memory.py` owns validation result construction.
- `scripts/mcp_runtime_smoke.py` verifies the MCP setup-health path.
