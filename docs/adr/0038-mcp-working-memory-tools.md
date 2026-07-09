# ADR 0038: MCP Working Memory Tools

## Status

Accepted for the v2 draft.

## Context

The CLI already supports generated working snapshots and session handoffs under
`working/`. MCP clients could request token-budgeted context that includes those
files, but they could not read or update current working state without shelling
out to the CLI.

Working state is operational context. It is useful during an active task, but it
is not canonical durable memory and should not bypass review-first promotion.

## Decision

Expose four MCP tools:

- `memory.working_current` reads generated `working/current.json` when present.
- `memory.working_status` summarizes generated current state, recent-session
  state, and recent handoff metadata.
- `memory.working_snapshot` writes `working/current.json` and
  `working/recent-session.md`.
- `memory.working_handoff` writes a Markdown handoff under `working/handoffs/`.

Working reads and writes use the existing working-memory implementation, reject
symlinked `working/` path components, secret-scan rendered write content, bound
each text input to 12,000 characters, and return repository-relative paths.
These tools only read or write under generated `working/` state and do not
promote or mutate canonical memory.

## Benefits

- MCP clients can keep task-local state without direct filesystem assumptions.
- Handoffs become available to local agent workflows that only use MCP tools.
- Existing CLI safety and secret scanning behavior remains the single write
  path.

## Limitations

- Working state is generated operational context, not reviewed durable fact.
- The tools do not resolve conflicts or promote lessons into durable memory.
- The tools do not expose private or sensitive canonical memories.

## Future Risks

- Clients may over-trust generated working state unless skills and docs keep the
  review boundary explicit.
- Handoff files can accumulate and may need future retention or review tooling.
- Larger automated captures may need structured fields instead of a single notes
  string.

## Dependencies

- ADR 0004 keeps consolidation review-first instead of direct durable mutation.
- ADR 0015 defines durable provenance requirements that working files do not
  satisfy by themselves.
- ADR 0021 requires MCP runtime smoke coverage for side-effecting tools.
- ADR 0031 requires every new ADR to include this dependency section.
