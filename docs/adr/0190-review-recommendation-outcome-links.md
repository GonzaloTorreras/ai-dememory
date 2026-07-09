# ADR 0190: Review Recommendation Outcome Links

Status: Accepted

## Context

ADR 0188 added advisory review recommendation artifacts, and ADR 0189 added a
read-only queue view for those artifacts. Reviewers could inspect a suggestion
and then run an explicit human-approved review command, but the accepted review
state did not preserve which recommendation was accepted.

That made audit trails weaker: the final conflict or false-positive review
state recorded reviewer metadata, but not the recommendation id, artifact path,
action, or whether the suggestion had exceeded the active review mode.

## Decision

Add optional recommendation links to explicit review outcome commands.

The CLI accepts `--recommendation-id rec_...` on:

- `ai-dememory false-positive ignore`;
- `ai-dememory false-positive unignore`;
- `ai-dememory conflict dismiss`; and
- `ai-dememory conflict resolve` for both `--keep` and `--merge-proposal`.

The MCP tools accept the same optional `recommendation_id` field on
`memory.false_positive_ignore`, `memory.false_positive_unignore`,
`memory.conflict_dismiss`, `memory.conflict_keep`, and
`memory.conflict_merge_proposal`.

Before writing review state, the implementation validates that the referenced
recommendation artifact exists and matches the expected kind, target id, and
accepted action. The stored review state records:

- `recommendation_id`;
- `recommendation_path`;
- `recommendation_action`; and
- `recommendation_policy_violation`.

The linked outcome still writes only review state or conflict proposal inbox
files. It does not modify the recommendation artifact, approve other
recommendations, or edit canonical memory.

## Benefits

- Accepted review outcomes can be traced back to the exact LLM/client
  recommendation artifact.
- Review reports and MCP receipts can render recommendation provenance without
  parsing inbox files.
- Policy-violation recommendations remain visible after a human accepts the
  outcome.
- Invalid or mismatched recommendation ids fail before review state is written.

## Limitations

- Links are optional; existing manual review commands still work without them.
- Recommendation artifacts are marked accepted/rejected by ADR 0191, but they
  are not archived by this link-only workflow.
- The link proves which artifact was referenced, not that the recommendation was
  correct.
- Only false-positive and conflict review outcomes are linked in this slice;
  inbox promotion and maintenance outcomes still need their own approval model.

## Future Work

- Add archive or cleanup support for stale recommendation artifacts after linked
  outcomes are reviewed.
- Extend recommendation links to inbox promotion and maintenance workflows when
  those workflows gain explicit review outcome commands.

## Dependencies

- ADR 0188 defines advisory recommendation artifacts.
- ADR 0189 defines read-only recommendation status.
- ADR 0191 defines accepted/rejected recommendation artifact status.
- ADR 0001 defines review and conflict workflows.
- ADR 0065 defines false-positive MCP receipt boundaries.
- ADR 0083, ADR 0084, and ADR 0085 define conflict MCP receipt boundaries.
- `scripts/review_memory.py` owns recommendation validation and review state.
- `mcp/server/memory_mcp.py` exposes linked recommendation receipts to clients.
