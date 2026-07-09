# ADR 0169: Hook Capture Review-Due Summary

Status: Accepted

## Context

ADR 0168 added a bounded frontmatter-only hook capture summary to
`memory.hook_status` and setup health. Hook capture candidates already include
`review_after` metadata, but the summary only reported counts and latest paths.

Without due-state fields, setup and plugin flows could not distinguish a new
capture from one whose review window had expired.

## Decision

Extend the hook capture summary with review-after status fields:

- `review_due_count`;
- bounded `review_due_paths`;
- `review_after_status_counts`; and
- per-latest-item `review_due` and `review_after_status`.

Statuses are `scheduled`, `due`, `missing`, or `invalid`. Missing review dates
are visible but not automatically due. Invalid dates are due so malformed
metadata is surfaced for review. `setup_health` adds a next action when due hook
captures exist.

The implementation still reads only hook candidate frontmatter under
`inbox/session-events/`. It does not inspect raw payload bodies or write files.

## Benefits

- Reviewers can see due hook capture work in the same setup-health flow as
  false-positive, stale suppression, and conflict review work.
- Plugin setup can route users to the session-event inbox when hook captures
  are overdue.
- Invalid hook capture metadata is visible without exposing raw payloads.

## Limitations

- The summary is not a full hook review queue or report.
- Due state is computed from the local date where the command runs.
- Existing malformed files are reported but not repaired.

## Future Work

- Add a dedicated hook capture review report if reviewers need durable handoff
  evidence.
- Add per-provider due filters if high-volume hook capture becomes common.

## Dependencies

- ADR 0141 defines hook event idempotency.
- ADR 0143 defines canonical JSON hook fingerprints.
- ADR 0167 exposes read-only hook status through MCP and setup health.
- ADR 0168 defines the bounded hook capture status summary.
- `scripts/hook_event.py` owns hook capture review-after classification.
