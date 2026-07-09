# ADR 0165: Review List Policy Metadata

Status: Accepted

## Context

ADR 0162 made disabled false-positive and conflict review workflows return empty
read/report results while rejecting writes. That behavior was safe, but an empty
list could mean either "the workflow is disabled" or "the workflow is enabled
and has no candidates." Clients had to make a second `review modes` or
`review plan` call to distinguish those states.

CLI JSON output had the same ambiguity for review reports.

## Decision

Add compact policy metadata to review listing responses:

- false-positive review JSON/MCP responses include `enabled` and `policy`;
- stale false-positive review JSON/MCP responses include `enabled` and
  `policy`; and
- conflict review JSON/MCP responses include `enabled` and `policy`.

The metadata is intentionally compact and specific to the returned workflow.
Detailed cross-workflow policy remains available through `review modes` and
`review plan`.

## Benefits

- Clients can distinguish disabled review workflows from empty enabled review
  queues in one call.
- CLI JSON and MCP responses now have consistent review policy metadata.
- The change is additive and keeps existing candidate arrays and counts.

## Limitations

- Plain-text CLI report output remains human-oriented and does not print the
  full policy metadata.
- Write receipts still report audit data only; callers should inspect list or
  mode/plan tools for policy.
- The metadata is a snapshot at call time and does not replace reading
  `.ai-dememory.toml` for full configuration review.

## Future Work

- Add structured policy metadata to generated Markdown reports if reviewers need
  offline report files to carry the same state.
- Add a dedicated review-policy command if policy grows beyond compact response
  metadata.

## Dependencies

- ADR 0161 defines review policy defaults.
- ADR 0162 enforces enabled review workflow boundaries.
- ADR 0163 and ADR 0164 wire conflict scan policy into validation and
  consolidation.
- `scripts/review_memory.py` owns CLI review JSON payloads.
- `mcp/server/memory_mcp.py` owns MCP review list schemas and responses.
