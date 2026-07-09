# ADR 0151: Scheduler Review Due Summary

## Status

Accepted

## Context

`memory.schedule_status` is the read-only MCP view for local maintenance
scheduler setup. ADR 0144 made it report invalid persisted schedule config
without executing host scheduler commands. ADR 0147 and ADR 0150 added
false-positive review due and stale suppression summaries to maintenance
status.

Users inspecting whether scheduled maintenance is configured also need to see
whether there is pending review work that scheduled maintenance would surface.
Without that summary, clients must call both scheduler status and maintenance
status to build one setup view.

## Decision

Add a read-only `review_due` object to `schedule_status` and MCP
`memory.schedule_status`. The payload reuses the same compact
`review_due_summary` used by maintenance status, including:

- current false-positive finding counts
- due suppression counts and bounded ids
- stale suppression counts and bounded ids
- `canonical_memory_updated=false`

`schedule_status` still does not run `systemctl`, `schtasks`, `launchctl`,
`crontab`, Docker, or maintenance jobs. Invalid schedule configuration still
returns `valid=false`, validation errors, no platform status commands, and the
review summary.

## Consequences

- MCP clients and plugin setup flows can show scheduler configuration and
  pending review work from one read-only call.
- Runtime smoke now protects the `review_due` field on normal and invalid
  schedule status responses.
- The field stays consistent with maintenance status because both use the same
  summary function.

## Limitations

- The summary depends on current secret-scan findings and stored suppression
  metadata; it is not a scheduler health check.
- The scheduler status CLI path that executes platform status commands is not
  changed by this decision.
- Review ids are bounded to keep setup payloads compact.

## Future Work

- Add a CLI-only dry-run status mode that returns the same structured scheduler
  payload without running platform status commands.
- Include conflict-review follow-up counts if maintenance status later exposes
  them.
- Consider a combined setup health report if users need one command that joins
  scheduler environment diagnostics, scheduler status, and review work.

## Dependencies

- ADR 0144 defines MCP schedule validation status.
- ADR 0147 defines maintenance false-positive review due summaries.
- ADR 0150 defines stale suppression counts in maintenance summaries.

## References

- `scripts/schedule_memory.py`
- `scripts/maintenance.py`
- `mcp/server/memory_mcp.py`
- `scripts/mcp_runtime_smoke.py`
