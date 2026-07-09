# ADR 0176: Hook Capture Date Window Filters

## Status

Accepted

## Context

ADR 0174 added provider, event, and review-status filters for hook capture
review queues. Large hook capture folders still need time-window scoping: a
reviewer may want only captures created during a sprint, or only captures whose
`review_after` date falls in a due-review window.

The filter surface must stay frontmatter-only and must not read raw hook payload
bodies. Existing unfiltered summaries, reports, setup health, and MCP clients
must remain compatible.

## Decision

Add date-window filters to the shared hook capture summary helper:

- `created_from`
- `created_to`
- `review_after_from`
- `review_after_to`

The CLI exposes these as:

- `ai-dememory hooks captures --created-from <YYYY-MM-DD>`
- `ai-dememory hooks captures --created-to <YYYY-MM-DD>`
- `ai-dememory hooks captures --review-after-from <YYYY-MM-DD>`
- `ai-dememory hooks captures --review-after-to <YYYY-MM-DD>`

MCP `memory.hook_status` exposes the same filters as
`capture_created_from`, `capture_created_to`, `capture_review_after_from`, and
`capture_review_after_to`.

Date filters validate ISO `YYYY-MM-DD` values and reject inverted ranges.
Candidates with missing or invalid matching frontmatter dates are excluded from
date-filtered results. Summaries still include `filters`,
`unfiltered_total_count`, `reads_raw_payloads=false`, and `writes_files=false`.

## Benefits

- Reviewers can scope hook capture queues by sprint, incident window, or due
  review window without ad hoc file searches.
- CLI reports and MCP status stay aligned because they use the same helper.
- Existing callers see unchanged output unless they opt into filters.
- Raw hook payload bodies remain unread during selection.

## Limitations

- Date filters match frontmatter dates only; they do not inspect payload
  timestamps or raw event bodies.
- Missing or invalid candidate dates are excluded when a corresponding date
  filter is active.
- This does not add pagination or archive partitioning for very large folders.

## Future Risks

- Very large hook capture folders may still need date-partitioned archive paths
  or paginated MCP summaries.
- If clients need time-zone-aware timestamps, the date-only contract may need a
  separate timestamp filter rather than changing this behavior.

## Dependencies

- ADR 0168 defines frontmatter-only hook capture summaries.
- ADR 0174 defines provider, event, and review-status filters.
- ADR 0175 defines reviewed hook capture archival.
- `scripts/hook_event.py` owns date-window validation and filtering.
- `mcp/server/memory_mcp.py` exposes date-window MCP arguments.
