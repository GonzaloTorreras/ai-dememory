# ADR 0195: Maintenance Review Recommendation Summary

Status: Accepted

## Context

ADR 0188 added advisory review recommendation artifacts under
`inbox/review-recommendations/`, ADR 0189 added read-only recommendation
listing, and ADR 0191 added accepted/rejected outcome status on those
artifacts. Daily and weekly maintenance already reported false-positive review
due counts, conflict review counts, hook capture review due counts, and
generated artifact state, but not the recommendation queue.

That left schedulers and plugin workflows unable to tell whether advisory
recommendations still needed review unless they ran a separate review command.

## Decision

Add a compact `review_recommendations` summary to maintenance status, setup
health, and generated maintenance reports.

The summary is read-only and includes:

- total, pending, accepted, rejected, invalid, policy-violation, and
  human-approval counts;
- pending recommendation ids, bounded to 20;
- status counts and kind counts;
- latest creation time;
- side-effect flags showing that recommendations are not applied and canonical
  memory is not mutated.

Daily and weekly maintenance reports include the same summary and a top-level
`pending_review_recommendations` count. MCP `memory.maintenance_status` and
`memory.setup_health` expose the summary through their existing read-only
status payloads.

## Benefits

- Scheduler dashboards and plugin skills can surface pending advisory review
  work without shelling out to a second command.
- Review recommendation queues now have the same operational visibility as
  false-positive and conflict queues.
- Setup health can guide users toward closing pending or malformed advisory
  recommendations.
- The summary keeps the review-first boundary explicit: no recommendation is
  applied and no canonical memory is changed.

## Limitations

- The summary is intentionally compact and does not include full recommendation
  rationale or evidence; reviewers still use `ai-dememory review
  recommendations --json` or MCP `memory.review_recommendations` for details.
- Pending ids are bounded, so very large queues require the dedicated listing
  command.
- Outcome status remains reviewer supplied and is not an authenticated identity
  proof.

## Future Work

- Consider a generated offline recommendation packet if reviewers need a
  printable queue handoff.
- Revisit summary severity or priority fields if recommendation artifacts later
  gain prioritization metadata.

## Dependencies

- ADR 0188 defines advisory recommendation artifacts.
- ADR 0189 defines read-only recommendation status.
- ADR 0191 defines accepted/rejected recommendation outcomes.
- ADR 0196 defines CLI-only archival for accepted/rejected recommendation
  artifacts.
- `scripts/review_memory.py` owns recommendation artifact parsing.
- `scripts/maintenance.py` owns maintenance status and reports.
- `scripts/setup_plan.py` owns setup health next actions.
- `mcp/server/memory_mcp.py` exposes the read-only status payloads.
