# ADR 0085: MCP Conflict Keep Reviewer Receipts

## Status

Accepted.

## Context

`memory.conflict_keep` accepts a reviewer and records the keep decision in
`.ai-dememory-ignore.toml`. Before this decision, its MCP receipt returned the
conflict id, keep target, status, decision, and canonical-memory boundary, but
omitted the reviewer metadata that clients already receive from conflict
dismiss and merge-proposal receipts.

That made keep receipts weaker audit artifacts for MCP clients. A client could
confirm that canonical memory stayed unchanged, but it could not render who
reviewed the keep decision without separately reading the ignore TOML.

## Decision

Return reviewer metadata from `memory.conflict_keep`.

The receipt includes:

- `path`
- `id`
- `keep`
- `status`
- `decision`
- `reviewer`
- `reviewed_at`
- `canonical_memory_updated`

`canonical_memory_updated` remains `false`; the tool records review state only
and does not edit, delete, supersede, archive, or promote canonical memories.

## Benefits

- Makes all MCP conflict write receipts consistent for clients.
- Lets clients display the reviewer and review timestamp without parsing TOML.
- Gives runtime smoke a direct assertion that keep decisions are reviewed and
  audit-ready.

## Limitations

- The receipt does not prove the selected memory is the best canonical answer.
- The reviewer value is still supplied by the caller and is not an identity
  proof.
- The receipt records review metadata only; any canonical memory changes still
  require separate human action.

## Future Risks

- If conflict review gains authenticated identities, the receipt may need
  separate display-name and principal fields.
- Batch conflict resolution should return one receipt per conflict with
  partial-failure reporting.
- If clients add one-click canonical edits, they must keep that path separate
  from this review-state-only keep tool.

## Dependencies

- ADR 0001 defines review and conflict workflows.
- ADR 0064 defines the MCP conflict keep resolution boundary.
- ADR 0083 defines structured MCP conflict-dismiss receipts.
- ADR 0084 defines structured MCP conflict merge-proposal receipts.
- `scripts/review_memory.py` remains the source of conflict review state.
