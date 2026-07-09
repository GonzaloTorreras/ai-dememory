# ADR 0084: MCP Conflict Merge Proposal Receipts

## Status

Accepted.

## Context

Conflict review has three MCP write paths: dismiss, keep, and merge proposal.
After ADR 0083, dismiss and keep both return structured audit receipts. The
merge-proposal path still returned only the ignore-file path and generated
proposal path, so clients could not directly confirm the conflict id, review
state, reviewer, decision, timestamp, or canonical-memory boundary.

The merge-proposal tool writes two review artifacts: it updates
`.ai-dememory-ignore.toml` with `review_proposed` state and writes a Markdown
proposal under `inbox/conflict-resolution/`. Neither write mutates canonical
memory.

## Decision

Return a structured receipt from `memory.conflict_merge_proposal`.

The receipt includes:

- `path`
- `id`
- `status`
- `decision`
- `reviewer`
- `reviewed_at`
- `proposal_path`
- `canonical_memory_updated`

`canonical_memory_updated` is always `false`; the generated proposal still
requires human review and manual promotion before canonical memory changes.

## Benefits

- Completes consistent receipt behavior across all MCP conflict write tools.
- Lets clients render the proposal path and review state without parsing TOML.
- Gives runtime smoke a direct assertion that merge proposals stay review-first.

## Limitations

- The receipt does not mean the generated merge proposal is correct or approved.
- The proposal remains a Markdown draft in `inbox/conflict-resolution/`.
- If the source conflict disappears after detection changes, old proposal
  receipts may reference a stale conflict id.

## Future Risks

- If merge proposals gain richer schemas, the receipt may need a version field.
- Batch proposal generation should return one receipt per conflict with
  partial-failure reporting.
- If clients expose one-click apply of proposals, they must keep that separate
  from this review-first write path.

## Dependencies

- ADR 0001 defines review and conflict workflows.
- ADR 0064 defines structured MCP keep-decision receipts.
- ADR 0083 defines structured MCP conflict-dismiss receipts.
- `scripts/review_memory.py` remains the source of conflict review state.
