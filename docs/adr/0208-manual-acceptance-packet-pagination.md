# ADR 0208: Manual Acceptance Packet Pagination

Status: Accepted

## Context

ADR 0186 added `ai-dememory acceptance packet` as a generated reviewer packet
for human-only v2 release checks. ADR 0192 exposed the same packet over MCP
without writing files or recording evidence.

The manual acceptance registry is currently small, but the release checklist can
grow as distribution, install, and real-client acceptance work expands. Packet
rendering needs bounded sections before that registry becomes too large for
comfortable MCP display or PR handoff review.

## Decision

Add offset pagination to manual acceptance packet rendering for incomplete
acceptance items.

CLI:

- `ai-dememory acceptance packet --limit 50 --offset 50 --write-report`

MCP:

- `memory.acceptance_packet` accepts `limit` and `offset`.

The packet payload includes:

- `limit`;
- `returned_count`;
- `offset`;
- `next_offset`;
- `has_more`;
- paged incomplete `items`; and
- unchanged total `completed_count`, `blocked_count`, and `remaining_count`.

Completed items remain a compact summary in the Markdown packet. The paged
section is the reviewer fill-in workload: incomplete manual checks that still
need pass/block evidence. The packet remains guidance only and still reports
`records_evidence=false` and `writes_acceptance_records=false`.

## Benefits

- Reviewers can page large manual acceptance workloads without losing total
  readiness counts.
- MCP clients can present next-page actions from structured fields.
- CLI and MCP keep sharing the same packet renderer.
- No new state files, indexes, or background tasks are required.

## Limitations

- Pagination is offset-based; newly recorded acceptance evidence can shift later
  pages.
- Generated packet files contain only the selected incomplete item page.
- Pagination does not record acceptance evidence or prove release readiness.

## Future Work

- Add stable cursor tokens only if offset pagination proves insufficient.
- ADR 0211 adds CLI-only timestamped packet archives.
- ADR 0209 adds optional reviewer and PR URL packet metadata.

## Dependencies

- ADR 0186 defines the generated manual acceptance packet.
- ADR 0192 defines read-only MCP manual acceptance packet rendering.
- ADR 0209 defines optional manual acceptance packet metadata.
- ADR 0211 defines manual acceptance packet archives.
- `scripts/manual_acceptance.py` owns acceptance planning, packets, templates,
  and evidence recording.
- `mcp/server/memory_mcp.py` exposes MCP packet pagination fields.
- `scripts/mcp_runtime_smoke.py` verifies default packet pagination metadata.
