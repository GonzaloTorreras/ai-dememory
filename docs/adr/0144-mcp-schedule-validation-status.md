# ADR 0144: MCP Schedule Validation Status

## Status

Accepted

## Context

ADR 0142 added scheduler input validation and made `schedule_status` report
invalid persisted config with `valid=false`, `validation_errors`, and no
platform status commands. MCP clients and Codex plugin skills depend on the MCP
tool schema to know which fields are stable.

Without schema and smoke coverage, `memory.schedule_status` could return the
new fields at runtime while the MCP contract still suggested they were
incidental, making plugin workflows weaker for invalid scheduler config.

## Decision

Add `valid` and `validation_errors` to the `memory.schedule_status` output
schema and require them in the MCP contract.

Extend MCP runtime smoke coverage with an invalid persisted scheduler config.
The smoke asserts that `memory.schedule_status` returns `valid=false`,
validation errors, and no platform status commands while remaining read-only.

## Consequences

- MCP clients can rely on schedule validation fields being present.
- Plugin setup and maintenance skills can distinguish invalid config from a
  missing host scheduler.
- Runtime smoke now covers both normal status-command planning and invalid
  config reporting.

## Limitations

- The MCP tool still does not query host scheduler health.
- Validation errors cover scheduler config syntax only, not whether Docker or
  platform scheduler binaries exist.
- Existing clients that ignored unknown fields continue to work, but clients
  with cached schemas may need refresh.

## Future Work

- Add a read-only environment diagnostic for Docker and host scheduler
  availability if users need stronger setup troubleshooting.
- Add a repair command separately if invalid config becomes common in practice.
- Keep MCP schedule tools read-only unless the user explicitly chooses CLI
  scheduler installation.

## Dependencies

- ADR 0066 defines read-only MCP scheduler status.
- ADR 0133 defines scheduler and plugin setup boundaries.
- ADR 0142 defines scheduler input validation.

## References

- `mcp/server/memory_mcp.py`
- `scripts/mcp_runtime_smoke.py`
- `mcp/server/README.md`
