# ADR 0114: Recall Review Resolved Summary

## Status

Accepted.

## Context

ADR 0112 and ADR 0113 closed the recall-miss lifecycle for promoted,
rejected, and dismissed misses. The review planner then ignored those files so
weekly review stayed focused on unresolved work.

That made pending queues cleaner, but it also hid recent review activity from
release handoffs and MCP clients. A reviewer could not see whether the queue was
empty because no misses existed, or because recent misses were already reviewed.

## Decision

Extend recall review planning with a bounded resolved-miss summary:

- `resolved_count`
- `recent_resolved_misses`

Each resolved summary includes path, status, reviewer metadata, query,
expected target, review reason, promoted fixture id when present, and
redaction state. The CLI exposes a `--resolved-limit` option on
`ai-dememory recall-fixtures review-plan`, and MCP `memory.recall_review_plan`
accepts the same bounded limit.

Release evidence includes the resolved count and recent resolved misses in the
Recall Review Plan section.

## Benefits

- Keeps pending review focused without losing audit visibility.
- Lets release handoffs show recent recall review activity.
- Gives MCP/plugin clients enough context to explain why the pending queue is
  empty or smaller than expected.
- Keeps output bounded for long-lived recall-feedback inboxes.

## Limitations

- The summary is read-only and does not archive or delete resolved miss files.
- The default recent list is a sample; `resolved_count` remains the total
  count.
- A rejected or dismissed miss still does not satisfy fixture freshness. Only a
  reviewed promotion adds recall-quality evidence.

## Future Risks

- If recall feedback grows large, scanning all miss files for every plan may
  need an indexed review-state cache.
- If resolved miss history becomes part of compliance evidence, the summary may
  need stable pagination instead of a bounded recent list.
- If review reasons become structured, older free-text reasons will need
  migration or compatibility rendering.

## Dependencies

- ADR 0045 defines recall fixture review planning.
- ADR 0112 defines promoted source-miss closure.
- ADR 0113 defines rejected and dismissed source-miss closure.
- `scripts/recall_fixtures.py` owns recall review state.
- `scripts/release_evidence.py` renders the release handoff summary.
