# ADR 0178: MCP Validate Status

Status: Accepted

## Context

ADR 0177 added structured `ai-dememory validate --json` output for local
automation. MCP clients already consume read-only health tools such as
`memory.doctor`, `memory.setup_health`, and `memory.provenance_status`, but they
still needed to shell out separately to inspect validation errors, memory
counts, and validate-time conflict scan state.

Validation is a useful readiness signal for local clients, but it must not
write reports, mutate review state, or promote memory.

## Decision

Expose `memory.validate_status` as a read-only MCP tool with no input
arguments. It returns the same structured payload as `ai-dememory validate
--json`, including:

- `ok` and `exit_code`;
- `memory_count`;
- `messages` and `errors`; and
- `conflict_review` scan availability, status, counts, and blocking state.

The tool reuses the CLI validation result builder instead of reimplementing
frontmatter or conflict policy logic inside the MCP server.

## Benefits

- MCP clients can inspect validation status without parsing text output.
- The validation contract stays consistent between CLI and MCP surfaces.
- Runtime smoke now verifies the validation status path in a fixture vault.
- The tool remains read-only and preserves the review-first memory contract.

## Limitations

- The tool reports conflict counts and policy state, not full conflict details.
- Active conflicts stay non-blocking until a severity-aware validation policy
  exists.
- The MCP output schema currently keeps `conflict_review` as a generic object
  because status-specific fields differ by path.

## Future Risks

- If validation becomes severity-aware, MCP callers must treat `exit_code` and
  `conflict_review.blocking` as authoritative instead of assuming active
  conflicts are warnings.
- If detailed conflict evidence is exposed later, it should be added without
  removing the existing top-level fields.

## Dependencies

- ADR 0163 defines validate-time conflict scan behavior.
- ADR 0177 defines the structured validation payload.
- `scripts/validate_memory.py` owns validation result construction.
- `mcp/server/memory_mcp.py` owns MCP tool exposure.
- `scripts/mcp_runtime_smoke.py` verifies the runtime tool path.
