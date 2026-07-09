# ADR 0167: Hook Status In MCP Setup Health

Status: Accepted

## Context

The v2 plugin setup flow already exposes read-only MCP tools for hook event
lists and hook config fragments. The CLI also has `ai-dememory hooks list`,
which reports whether managed Codex or Claude instruction blocks are installed.

Plugin and MCP setup flows still could not inspect that managed-block status
without shelling out to the CLI. That made hook setup less complete than the
scheduler and provider setup surfaces, which already expose read-only status
tools.

## Decision

Expose managed hook instruction status through:

- MCP `memory.hook_status`; and
- `memory.setup_health` / `ai-dememory setup health --json`.

The status is read-only. It reports supported clients, installed count,
per-client instruction path, installed state, supported events, and explicit
side-effect flags. It does not install hooks, edit instruction files, read
client settings, capture hook payloads, or write inbox files.

## Benefits

- Plugin setup can show hook status alongside scheduler, provider, maintenance,
  and review health in one read-only response.
- MCP clients no longer need to shell out to inspect managed hook blocks.
- The behavior reuses the existing CLI hook-status implementation, keeping CLI
  and MCP status aligned.

## Limitations

- The status only detects managed instruction blocks in `AGENTS.md` and
  `CLAUDE.md`; it does not inspect client-specific settings files.
- It does not prove that a client is actually executing hooks.
- Hook capture inbox health remains a separate review concern.

## Future Work

- Add a bounded hook capture summary if reviewers need counts for recent
  `inbox/session-events/` candidates.
- Add explicit client-settings diagnostics only if clients expose a stable local
  configuration contract.

## Dependencies

- ADR 0006 defines managed hook instruction blocks.
- ADR 0133 defines the scheduler and plugin setup boundary.
- ADR 0153 defines read-only setup health.
- `scripts/hook_event.py` owns hook instruction status.
- `scripts/setup_plan.py` owns setup health.
- `mcp/server/memory_mcp.py` owns MCP tool schemas.
