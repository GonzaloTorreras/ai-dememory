# ADR 0081: MCP False-Positive Unignore Receipts

## Status

Accepted.

## Context

The CLI supports both sides of false-positive review state:
`ai-dememory false-positive ignore` and `ai-dememory false-positive unignore`.
The MCP server exposed only `memory.false_positive_ignore`, so MCP clients could
record a reviewed suppression but could not record that a suppression had been
reviewed and removed.

This made review state asymmetric and forced clients to shell out to the CLI for
the unignore path.

## Decision

Expose `memory.false_positive_unignore` as an MCP tool.

The tool calls the existing `unignore_false_positive` implementation and writes
only `.ai-dememory-ignore.toml`. It returns a structured receipt with:

- `path`
- `id`
- `ignored`
- `reviewer`
- `reviewed_at`
- `review_after`
- `canonical_memory_updated`

`canonical_memory_updated` is always `false` because the tool does not edit,
delete, promote, or rewrite Markdown memory.

## Benefits

- Completes the MCP false-positive review lifecycle.
- Lets clients show an auditable unignore receipt without parsing TOML.
- Keeps ignore and unignore behavior backed by the same CLI implementation.
- Preserves the boundary that canonical memory is not mutated.

## Limitations

- The tool records review state; it does not prove that the finding is or is not
  a real secret.
- It does not remove the finding source. If the source text remains, future
  scans will still report the finding as active.
- It does not include the reason field in the receipt, matching the existing
  ignore receipt's conservative rendering behavior.

## Future Risks

- If suppression state moves out of `.ai-dememory-ignore.toml`, both false
  positive receipt tools should keep stable output or add a version field.
- Clients may need batch unignore support; that should return one receipt per
  finding with partial-failure reporting.
- If the finding id changes because scanner rules change, stale unignore entries
  may remain in the ignore file.

## Dependencies

- ADR 0065 defines structured receipts for `memory.false_positive_ignore`.
- ADR 0001 defines the review workflow and keeps suppressions review-gated.
- `scripts/review_memory.py` remains the source of false-positive review state.
