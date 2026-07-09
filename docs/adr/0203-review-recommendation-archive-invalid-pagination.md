# ADR 0203: Review Recommendation Archive Invalid Pagination

Status: Accepted

## Context

ADR 0202 added offset pagination for valid archived review recommendation
records. The same archive status payload also reports malformed archived
artifacts, but those invalid entries were only bounded by the recommendation
page `limit` and always started at the first malformed file.

Large archives can accumulate several malformed files during manual migration,
partition experiments, or interrupted edits. Reviewers need to page those files
without increasing the normal recommendation page size or scanning the archive
outside the tool.

## Decision

Add a separate malformed artifact cursor to review recommendation archive
status.

CLI:

- `ai-dememory review recommendations-archive-status --limit 50 --invalid-offset 50`

MCP:

- `memory.review_recommendation_archive_status` accepts `invalid_offset`.

The status payload now includes:

- `invalid_returned_count`;
- `invalid_offset`;
- `invalid_next_offset`;
- `invalid_has_more`.

`invalid_offset` must be zero or greater. Existing calls keep
`invalid_offset=0`, so valid recommendation pagination and existing consumers
remain compatible. Malformed artifact paths are sorted before paging so repeated
reads are deterministic while the archive contents stay unchanged.

## Benefits

- Reviewers can walk large malformed archive queues in bounded pages.
- Valid recommendation history and malformed artifact review have independent
  cursors.
- MCP clients can present a separate "next malformed page" action.
- The archive remains Markdown-only; no stateful cursor files or indexes are
  introduced.

## Limitations

- Pagination is still offset-based; archive edits between page reads may shift
  malformed entries.
- `limit` is shared by valid and malformed pages to keep the CLI and MCP schema
  small.
- The command reports malformed artifacts but does not repair them.

## Future Work

- Add stable cursor tokens only if offset pagination proves insufficient.
- Add repair helpers only after recurring malformed archive patterns are known.

## Dependencies

- ADR 0197 defines CLI archive status.
- ADR 0200 defines MCP archive status.
- ADR 0202 defines valid archive record pagination.
- `scripts/review_memory.py` owns archive status sorting and pagination.
- `mcp/server/memory_mcp.py` exposes MCP `invalid_offset`.
- `scripts/mcp_runtime_smoke.py` verifies default invalid pagination fields.
