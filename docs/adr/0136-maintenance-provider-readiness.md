# ADR 0136: Maintenance Provider Readiness

## Status

Accepted

## Context

Daily maintenance can import enabled provider chat/session files into review
inboxes. Before users install recurring maintenance, they need to know whether
configured provider paths are ready without triggering an import or reading chat
files.

`memory.providers_status` already answered this directly, but
`maintenance status` only exposed raw provider config alongside schedule and
artifact status. That made the scheduler review path less complete than the
provider setup path.

## Decision

Add a `provider_readiness` object to `ai-dememory maintenance status` and MCP
`memory.maintenance_status`. The value is the same read-only readiness payload
returned by `providers_status`.

Also make `providers_status` explicit about side effects by returning:

- `reads_provider_files=false`
- `writes_import_candidates=false`

## Consequences

- Reviewers can inspect one maintenance status payload before enabling daily or
  weekly jobs.
- Codex plugin maintenance workflows can explain which providers will import
  during scheduled maintenance without reading provider contents.
- Existing raw provider config remains available for compatibility.

## Limitations

- Readiness checks only verify configuration, enabled state, and path
  existence; they do not inspect chat file contents.
- A provider can be ready at status time and fail later if files move or
  permissions change.
- Import counts are still available only after a maintenance run or explicit
  `import-chats` command.

## Future Work

- Add provider-specific import dry-run counts if users need preflight file
  counts without writing inbox candidates.
- Include provider readiness in generated maintenance reports if reviewers need
  a permanent pre-run snapshot.
- Keep raw provider content out of status surfaces unless a separate privacy
  review approves a bounded preview.

## Dependencies

- ADR 0067 defines read-only MCP provider status.
- ADR 0078 defines provider setup planning.
- ADR 0133 defines scheduler and plugin setup boundaries.

## References

- `scripts/maintenance.py`
- `scripts/provider_import.py`
- `mcp/server/memory_mcp.py`
