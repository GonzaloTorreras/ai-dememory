# ADR 0206: Review Recommendation Outcome Report Pagination

Status: Accepted

## Context

ADR 0204 added the CLI-generated recommendation outcome sign-off report, and
ADR 0205 exposed the same packet over MCP without writing files. Both returned
the complete reviewed recommendation set and all malformed active
recommendation artifacts in one payload.

Large review queues need bounded pages so reviewers and MCP clients can inspect
reviewed recommendation outcomes without rendering one oversized Markdown
packet. Archive status already uses offset pagination for valid and malformed
archive artifacts.

## Decision

Add offset pagination to the active recommendation outcome report.

CLI:

- `ai-dememory review recommendation-outcomes --limit 50 --offset 50 --json`
- `ai-dememory review recommendation-outcomes --limit 50 --invalid-offset 50 --json`

MCP:

- `memory.review_recommendation_outcome_report` accepts `limit`, `offset`, and
  `invalid_offset`.

The shared report payload includes:

- `limit`, `offset`, `next_offset`, `has_more`, and `returned_count` for valid
  reviewed recommendation records;
- `invalid_offset`, `invalid_next_offset`, `invalid_has_more`, and
  `invalid_returned_count` for malformed active recommendation artifacts; and
- unchanged side-effect flags proving the report does not apply review
  decisions, archive artifacts, or mutate canonical memory.

Both cursors default to `0`. The same `limit` bounds valid and malformed pages.
`offset` and `invalid_offset` must be zero or greater.

## Benefits

- Reviewers can page large active recommendation outcome queues before
  archival.
- MCP clients can offer explicit next-page actions without custom filesystem
  scans.
- CLI and MCP continue to share one report payload and Markdown renderer.
- No new state files, cursor stores, or generated indexes are required.

## Limitations

- Pagination is offset-based; active recommendation changes between page reads
  may shift records.
- One generated CLI report file contains only the selected page.
- The report still covers active recommendation inbox artifacts; archived
  history remains available through archive status.

## Future Work

- Add stable cursor tokens only if offset pagination proves insufficient.
- Add section-specific limits only if valid and malformed page sizes need to
  diverge.

## Dependencies

- ADR 0204 defines the CLI outcome report.
- ADR 0205 defines MCP outcome report rendering.
- ADR 0202 and ADR 0203 define archive status pagination patterns.
- `scripts/review_memory.py` owns outcome report sorting and pagination.
- `mcp/server/memory_mcp.py` exposes MCP pagination parameters.
- `scripts/mcp_runtime_smoke.py` verifies default pagination fields.
