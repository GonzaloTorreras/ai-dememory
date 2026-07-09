# ADR 0172: Hook Capture Review Outcomes

## Status

Accepted

## Context

Hook capture status, due counts, and review reports make
`inbox/session-events/` visible, but reviewers still had to hand-edit Markdown
to close a capture that did not need durable promotion. That made weekly hook
capture review noisier because reviewed captures could continue to appear as
due when their `review_after` date passed.

The review outcome must not promote memory, read raw payload bodies, or write
outside the hook capture inbox.

## Decision

Add `ai-dememory hooks review` as a CLI-only receipt command. It accepts a
capture path under `inbox/session-events/`, a reviewer, a reason, and one of:

- `reviewed`
- `rejected`
- `dismissed`

The command writes only frontmatter fields on the selected capture:

- `reviewed: true`
- `review_status`
- `reviewed_by`
- `reviewed_at`
- `review_reason`

The receipt metadata is secret-scanned before writing. The command returns
`canonical_memory_updated=false`.

Hook capture summaries and reports now include `pending_count`,
`resolved_count`, `review_status_counts`, and per-capture review outcome fields.
Resolved captures no longer count as review-due.

## Benefits

- Weekly review can close hook captures without hand-editing Markdown.
- Review-due counts stay focused on unresolved session-event candidates.
- The review action is auditable and path-bounded.
- The hook MCP setup/status surface remains read-only.

## Limitations

- This does not promote hook content into canonical memory.
- This does not delete rejected or dismissed capture files.
- MCP hook capture review receipts were intentionally left for a separate
  approval-gated tool decision.

## Future Risks

- Review receipts may need immutable audit export if hook capture review becomes
  part of a formal release evidence process.

## Dependencies

- ADR 0169 defines hook capture review-after due-state classification.
- ADR 0170 defines hook capture review reports.
- ADR 0171 defines weekly maintenance hook capture report generation.
- `scripts/hook_event.py` owns hook capture review receipts.
