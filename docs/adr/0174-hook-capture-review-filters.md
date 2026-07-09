# ADR 0174: Hook Capture Review Filters

## Status

Accepted

## Context

Hook capture review now has status summaries, generated reports, CLI review
receipts, and MCP review receipts. As `inbox/session-events/` grows, reviewers
need to focus on one provider, event type, or lifecycle state without opening
raw payload bodies or hand-filtering Markdown files.

The filter surface must stay frontmatter-only and must not change default
summary behavior for setup health, maintenance status, release evidence, or
existing MCP clients.

## Decision

Add optional provider, event, and review-status filters to the shared
`hook_capture_summary` helper. The filters are exposed through:

- `ai-dememory hooks captures --provider <provider>`
- `ai-dememory hooks captures --event <event>`
- `ai-dememory hooks captures --review-status <status>`
- MCP `memory.hook_status` arguments `capture_provider`, `capture_event`, and
  `capture_review_status`

Review-status filters support `pending`, `resolved`, `reviewed`, `rejected`,
and `dismissed`. `resolved` matches any reviewed, rejected, or dismissed
capture. Filtered summaries continue to include `reads_raw_payloads=false` and
`writes_files=false`, and they add:

- `filters`
- `unfiltered_total_count`

Reports generated with `--write-report` use the same filtered summary and print
the active filters in the summary section.

## Benefits

- Reviewers can triage high-volume hook capture inboxes without shelling out to
  ad hoc file searches.
- CLI reports and MCP status stay aligned because both use the same helper.
- Existing default summary behavior remains unchanged when no filters are set.
- Clients can display scoped counts while still showing the full inbox size.

## Limitations

- Filters match frontmatter only; they never search raw hook payload bodies.
- Malformed frontmatter candidates are still reported as inbox health evidence
  because they cannot be safely classified by provider, event, or status.
- This does not archive or delete reviewed captures.

## Future Risks

- Very large hook capture folders may still need pagination or archive
  partitioning beyond these frontmatter filters.

## Dependencies

- ADR 0168 defines frontmatter-only hook capture summaries.
- ADR 0170 defines hook capture review reports.
- ADR 0172 defines hook capture review lifecycle statuses.
- ADR 0173 exposes MCP hook capture review receipts.
- `scripts/hook_event.py` owns hook capture filtering and report rendering.
- `mcp/server/memory_mcp.py` exposes filtered hook status arguments.
