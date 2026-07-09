# ADR 0150: Maintenance Stale Suppression Summary

## Status

Accepted

## Context

ADR 0149 added a dedicated stale false-positive suppression audit for ignored
`false_positives.<id>` sections whose current scanner finding no longer exists.
That command is useful during focused review, but routine maintenance still only
surfaced current false-positive review-due counts.

Scheduled daily and weekly maintenance should show stale suppressions in the
same broad status payload operators already inspect for provider readiness,
generated artifacts, and review due work.

## Decision

Extend the read-only `review_due` maintenance summary returned by
`ai-dememory maintenance status`, MCP `memory.maintenance_status`, and
generated maintenance reports with bounded stale suppression fields:

- `stale_suppressions`
- `stale_ids`
- `stale_review_due`
- `stale_review_due_ids`

The summary reuses the current false-positive review scan when available so
maintenance does not rescan only to calculate stale suppressions.

Installed package and Docker smoke validation now require
`review_due.stale_suppressions` to be present.

## Consequences

- Routine maintenance surfaces obsolete suppressions without requiring a
  separate focused review command.
- MCP clients can show stale-suppression work from `memory.maintenance_status`.
- Package and Docker smoke catch regressions in the expanded maintenance
  status contract.

## Limitations

- The summary still does not remove stale suppressions. Reviewers must use the
  explicit false-positive unignore workflow after review.
- Stale ids are bounded to keep maintenance status compact.
- Stale suppressions are not automatically release blockers; they are review
  signals unless a later release policy makes them blocking.

## Future Work

- Include stale suppression review in final manual acceptance evidence.
- Add a reviewed batch-unignore proposal flow if stale suppressions become
  common.
- Consider a combined setup health report if users need one command that joins
  scheduler environment diagnostics, scheduler status, and review work.

ADR 0151 later includes the maintenance review summary in scheduler status.

## Dependencies

- ADR 0055 defines generated artifact visibility in maintenance status.
- ADR 0056 and ADR 0057 define installed and Docker maintenance status smoke.
- ADR 0147 defines the `review_due` maintenance summary.
- ADR 0149 defines stale false-positive suppression audits.

## References

- `scripts/maintenance.py`
- `scripts/review_memory.py`
- `scripts/install_smoke.py`
- `mcp/server/memory_mcp.py`
