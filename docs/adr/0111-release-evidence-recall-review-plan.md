# ADR 0111: Release Evidence Recall Review Plan

## Status

Accepted.

## Context

ADR 0110 added recall fixture freshness to release evidence and introduced a
`recall_fixture_review` release blocker. That made the quality blocker visible,
but the actionable review details still required a separate
`ai-dememory recall-fixtures review-plan` command.

Final v2 handoffs should be self-contained enough for a reviewer to see the
blocker and the next recall-review actions in one artifact, just like manual
acceptance blockers include the manual acceptance plan.

## Decision

Embed the read-only recall fixture review plan in release evidence as
`recall_fixture_review_plan`.

The existing `recall_fixture_freshness` field remains for compatibility and
quick status checks. The `recall_fixture_review` blocker now carries the full
review plan payload so consumers can inspect freshness, pending miss files,
invalid miss files, and next actions without running a second command.

The Markdown report renders a `Recall Review Plan` section directly after recall
fixture freshness.

## Benefits

- Makes the final release handoff more actionable for recall-quality review.
- Reuses the canonical review planner from `scripts/recall_fixtures.py`.
- Keeps release evidence read-only while surfacing pending and malformed recall
  miss files.

## Limitations

- The review plan still does not promote fixtures or resolve misses.
- The report can become stale after a reviewer captures, fixes, or promotes a
  miss.
- The plan only covers local `inbox/recall-feedback/` files and the configured
  fixture JSON, not external retrieval telemetry.

## Future Risks

- If multiple recall fixture suites are introduced, the field should become a
  list or map keyed by suite name.
- If release evidence grows too large, verbose pending miss details may need a
  compact mode.
- If review state moves out of Markdown inbox files, this field must follow the
  same canonical planner backend.

## Dependencies

- ADR 0034 defines recall fixture freshness status.
- ADR 0045 defines the read-only recall fixture review plan.
- ADR 0110 defines recall freshness in release evidence.
- `scripts/recall_fixtures.py` remains the canonical recall review planner.
- `scripts/release_evidence.py` remains the final release readiness aggregator.
