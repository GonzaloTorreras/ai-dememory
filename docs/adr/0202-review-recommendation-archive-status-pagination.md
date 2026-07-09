# ADR 0202: Review Recommendation Archive Status Pagination

Status: Accepted

## Context

ADR 0197 and ADR 0200 added CLI and MCP archive status for advisory review
recommendations. ADR 0201 added optional recursive scans for partitioned
archives. Those read models used a bounded `limit`, but they did not expose a
cursor or offset for a reviewer to continue through large archive histories.

Reviewers need a simple way to page archived recommendation history without
changing the archive format or adding stateful cursors. ADR 0203 adds a
separate cursor for malformed archived artifacts.

## Decision

Add offset pagination to review recommendation archive status.

CLI:

- `ai-dememory review recommendations-archive-status --limit 50 --offset 50`

MCP:

- `memory.review_recommendation_archive_status` accepts `limit` and `offset`.

The status payload now includes:

- `offset`;
- `next_offset`;
- `has_more`;
- `returned_count`.

`offset` must be zero or greater. Existing calls keep `offset=0`, so current
flat and recursive archive status behavior remains compatible.

## Benefits

- Large archived recommendation histories can be reviewed in bounded pages.
- MCP clients can present "next page" actions without custom filesystem scans.
- Pagination works with recursive partition scans and existing filters.
- No additional state files, cursors, or generated indexes are required.

## Limitations

- Pagination is offset-based; archive changes between page reads may shift
  records.
- Malformed artifact reporting is paged separately by ADR 0203.
- Restore planning still targets one recommendation id and does not need paging.

## Future Work

- Add stable cursor tokens only if offset pagination proves insufficient.

## Dependencies

- ADR 0197 defines CLI archive status.
- ADR 0200 defines MCP archive status.
- ADR 0201 defines optional recursive archive scans.
- ADR 0203 defines malformed archive artifact pagination.
- `scripts/review_memory.py` owns archive status sorting and pagination.
- `mcp/server/memory_mcp.py` exposes MCP `offset`.
- `scripts/mcp_runtime_smoke.py` verifies default pagination fields.
