# ADR 0207: Recall Review Packet Pagination

Status: Accepted

## Context

ADR 0187 added the generated CLI recall review packet, and ADR 0193 exposed the
same packet as read-only MCP guidance. Both rendered all pending recall misses
and malformed miss files in one Markdown packet.

Weekly recall review can accumulate multiple pending misses and malformed
artifacts under `inbox/recall-feedback/`. MCP clients and generated reports need
bounded packets with enough metadata to request the next page without parsing
Markdown.

## Decision

Add offset pagination to recall review packet rendering.

CLI:

- `ai-dememory recall-fixtures packet --limit 50 --pending-offset 50 --write-report`
- `ai-dememory recall-fixtures packet --limit 50 --invalid-offset 50 --write-report`

MCP:

- `memory.recall_review_packet` accepts `limit`, `pending_offset`, and
  `invalid_offset`.

The shared packet plan includes:

- `limit`;
- `pending_returned_count`, `pending_offset`, `pending_next_offset`, and
  `pending_has_more`;
- `invalid_returned_count`, `invalid_offset`, `invalid_next_offset`, and
  `invalid_has_more`;
- paged `pending_misses` and `invalid_misses`; and
- unchanged total `pending_count`, `invalid_count`, and side-effect flags.

The same `limit` bounds pending and malformed pages. Offsets default to `0` and
must be zero or greater. The packet still includes the bounded recent resolved
miss summary controlled by `resolved_limit`.

## Benefits

- Reviewers can inspect high-volume recall miss queues in bounded packets.
- MCP clients can present next-page controls from structured fields.
- CLI and MCP keep sharing the same packet renderer.
- Pagination does not add state files, indexes, or background tasks.

## Limitations

- Pagination is offset-based; files added or reviewed between page reads may
  shift later pages.
- A generated packet file contains only the selected pending and malformed
  pages.
- The packet remains guidance only; it does not promote fixtures, close misses,
  or write `quality/recall-fixtures.json`.

## Future Work

- Add stable cursor tokens only if offset pagination proves insufficient.
- Add separate pending and malformed page sizes only if one shared limit becomes
  awkward for real clients.
- ADR 0210 adds optional reviewer and PR URL packet metadata.

## Dependencies

- ADR 0187 defines the CLI recall review packet.
- ADR 0193 defines read-only MCP recall review packet rendering.
- ADR 0210 defines optional recall review packet metadata.
- `scripts/recall_fixtures.py` owns recall review planning and packet
  rendering.
- `mcp/server/memory_mcp.py` exposes MCP packet pagination fields.
- `scripts/mcp_runtime_smoke.py` verifies default packet pagination metadata.
