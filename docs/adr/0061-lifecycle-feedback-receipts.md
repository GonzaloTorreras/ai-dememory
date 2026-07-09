# ADR 0061: Lifecycle Feedback Receipts

Status: Accepted for the v2 draft.

## Context

The v2 operational loop records retrieval usage with `mark-seen` and usefulness
feedback with `outcome`. That generated lifecycle state influences search
ranking and maintenance artifacts, so clients need a clear receipt showing what
was recorded.

Before this ADR, MCP `memory.mark_seen` returned only `created_at`, and the CLI
`ai-dememory mark-seen` had only human-readable output. That made package
smoke, MCP smoke, and future plugin skills weaker because they could confirm a
timestamp but not which memory id or lifecycle path was updated.

## Decision

Return structured mark-seen receipts:

- CLI: `ai-dememory mark-seen ... --json`
- MCP: `memory.mark_seen`

Receipts include:

- `query`
- `memory_id` or `selected_memory_id`
- `score`
- `used_by`
- `lifecycle_updated`
- `created_at`

The existing text output remains unchanged for normal CLI use. Package install
smoke now exercises the JSON receipt against the install-smoke fixture memory,
and MCP runtime smoke verifies the selected memory id and lifecycle update flag.

## Benefits

- Makes retrieval feedback auditable by callers without opening SQLite.
- Lets installed-package and MCP smoke prove the lifecycle feedback path is
  wired, not just timestamped.
- Gives plugin skills a stable structured response for user-visible feedback.

## Limitations

- Receipts prove that a write was attempted and committed locally, not that the
  selected memory was semantically useful.
- The receipt can echo the query and caller label after secret scanning; callers
  still must avoid putting sensitive text in feedback.
- SQLite remains generated state, so lifecycle feedback is operational evidence,
  not canonical Markdown memory.

## Future Risks

- If feedback moves to a separate lifecycle database, the receipt shape should
  remain stable or be versioned.
- If clients need batch feedback, this single-record receipt may need a batch
  equivalent rather than overloading the current command.

## Dependencies

- ADR 0003 defines lifecycle scoring and outcome feedback.
- ADR 0021 requires runtime smoke coverage for lifecycle feedback tools.
- `scripts/lifecycle.py` and `mcp/server/memory_mcp.py` implement the CLI and
  MCP receipt paths.
