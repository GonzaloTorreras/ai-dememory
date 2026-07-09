# ADR 0191: Review Recommendation Outcome Status

Status: Accepted

## Context

ADR 0188 added advisory recommendation artifacts, ADR 0189 added read-only
recommendation status, and ADR 0190 linked accepted review outcomes back to
recommendation ids. That made accepted false-positive and conflict outcomes
traceable, but recommendation artifacts themselves still appeared pending unless
reviewers inferred closure from separate review state.

Reviewers need a direct way to close advisory recommendations as accepted or
rejected without applying the recommendation, mutating canonical memory, or
moving files into an archive. ADR 0204 adds an offline report for reviewed
recommendation outcomes.

## Decision

Add reviewed outcome status on recommendation artifacts.

The CLI command is:

```bash
ai-dememory review recommendation-outcome \
  --id rec_... \
  --status accepted \
  --reviewer "Your Name" \
  --reason "Accepted after review."
```

MCP exposes the same writer as `memory.review_recommendation_outcome`.

The command updates only the selected file under
`inbox/review-recommendations/`, adding:

- `outcome_status` (`accepted` or `rejected`);
- `outcome_reviewed_by`;
- `outcome_reviewed_at`;
- `outcome_reason`;
- `outcome_applies_review_decision=false`; and
- `outcome_writes_canonical_memory=false`.

`ai-dememory review recommendations` and `memory.review_recommendations` now
report pending, accepted, and rejected counts and can filter by outcome status.

## Benefits

- Reviewers can close advisory recommendations without changing canonical
  memory.
- Recommendation queues can distinguish pending work from reviewed suggestions.
- MCP clients get a bounded receipt for recommendation closure.
- Secret scanning remains enforced on reviewer and reason text before the
  artifact is rewritten.

## Limitations

- Closing a recommendation does not apply a false-positive suppression,
  conflict decision, promotion, or maintenance action.
- ADR 0196 later adds CLI-only archival for accepted/rejected recommendation
  artifacts.
- Outcome status is reviewer supplied and is not an authenticated identity
  proof.
- Existing linked review outcomes are not backfilled automatically.
- The offline outcome report is a generated sign-off artifact and does not
  apply or archive outcomes.

## Future Work

- Expose outcome report rendering over MCP only if real clients need the packet
  without invoking the local CLI.

## Dependencies

- ADR 0188 defines advisory recommendation artifacts.
- ADR 0189 defines read-only recommendation status.
- ADR 0190 defines links from review outcomes to recommendation ids.
- ADR 0195 adds maintenance and setup-health summaries for recommendation
  queues.
- ADR 0196 defines CLI-only archival for accepted/rejected recommendation
  artifacts.
- ADR 0204 defines the offline recommendation outcome report.
- `scripts/review_memory.py` owns recommendation artifact parsing and updates.
- `mcp/server/memory_mcp.py` exposes the MCP outcome writer.
