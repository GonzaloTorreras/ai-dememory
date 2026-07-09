# ADR 0062: Outcome Feedback Receipts

Status: Accepted for the v2 draft.

## Context

ADR 0061 made retrieval feedback auditable by returning structured
`mark-seen` receipts. The paired Phase 3 operation is `outcome`, which records
whether a memory was useful after retrieval.

Before this ADR, CLI and MCP outcome feedback returned only the memory id,
outcome, and timestamp. That confirmed a row was written, but it did not show
whether `--last` resolved from the retrieval log, whether lifecycle state was
updated, or how the positive and negative counters changed.

## Decision

Return structured outcome receipts:

- CLI: `ai-dememory outcome ... --json`
- MCP: `memory.outcome`

Receipts include:

- `memory_id`
- `target_source` (`explicit` or `last_seen`)
- `outcome`
- `note_recorded`
- `positive_outcomes`
- `negative_outcomes`
- `strength`
- `reward_factor`
- `lifecycle_updated`
- `created_at`

Outcome notes remain write-only feedback: they are secret scanned before being
stored, but the receipt returns only `note_recorded` and does not echo note
text. The existing human-readable CLI output remains unchanged unless `--json`
is requested.

## Benefits

- Makes usefulness feedback auditable without opening generated SQLite tables.
- Lets package and MCP smoke prove outcome feedback updates lifecycle counters.
- Gives plugin skills enough metadata to explain whether feedback targeted an
  explicit memory or the last retrieved memory.
- Keeps note text out of client-visible receipts while still confirming whether
  a note was stored.

## Limitations

- Receipts report local generated lifecycle state, not canonical Markdown
  memory.
- Counter values are point-in-time state after one write, not a complete history
  of outcome feedback.
- `target_source=last_seen` proves the retrieval log selected the target, not
  that the original retrieval was semantically correct.

## Future Risks

- If lifecycle state moves to a separate database, receipt fields should remain
  stable or be versioned.
- Batch outcome capture may need a separate receipt format with per-memory
  results and partial-failure handling.
- If outcome notes gain review workflows, receipts may need a reviewed-note id
  rather than a boolean `note_recorded` field.

## Dependencies

- ADR 0003 defines lifecycle scoring and outcome feedback.
- ADR 0061 defines the paired retrieval feedback receipt pattern.
- `scripts/lifecycle.py` and `mcp/server/memory_mcp.py` implement the CLI and
  MCP outcome receipt paths.
