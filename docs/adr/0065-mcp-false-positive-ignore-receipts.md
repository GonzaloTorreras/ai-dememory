# ADR 0065: MCP False-Positive Ignore Receipts

Status: Accepted for the v2 draft.

## Context

False-positive review suppresses reviewed secret-scan findings by writing
metadata to `.ai-dememory-ignore.toml`. The MCP tool
`memory.false_positive_ignore` already allowed clients to record a suppression,
but it returned only the ignore-file path.

That was enough to prove that a file changed, but not enough for MCP clients or
plugin skills to confirm which finding id was suppressed, who reviewed it,
whether a review-after date was recorded, or whether canonical memory stayed
unchanged. Other v2 feedback and review tools now return structured receipts,
so false-positive suppression should follow the same auditable pattern.

## Decision

Return a structured receipt from `memory.false_positive_ignore`.

The receipt includes:

- `path`
- `id`
- `ignored`
- `reviewer`
- `reviewed_at`
- `review_after`
- `canonical_memory_updated`

The tool continues to call the existing reviewed false-positive suppression
implementation. It writes only `.ai-dememory-ignore.toml`; it does not edit,
delete, promote, or rewrite Markdown memory. `canonical_memory_updated` is
always `false` for this tool.

## Benefits

- Lets MCP clients display an audit result without re-reading the ignore file.
- Makes reviewer and review-after metadata visible in runtime smoke and plugin
  workflows.
- Aligns false-positive suppression with other structured review receipts.
- Keeps the non-mutation boundary explicit for safety review.

## Limitations

- The receipt reports the local review state after writing; it does not prove
  that the finding was semantically safe to suppress.
- If the underlying secret-scan finding disappears, future review listings may
  no longer include the same id even though the ignore metadata remains.
- The receipt does not include the suppression reason to avoid encouraging
  clients to render reviewer-supplied text in unsafe contexts.

## Future Risks

- If suppression state moves out of `.ai-dememory-ignore.toml`, the receipt
  should remain stable or gain a version field.
- Stale suppressions may need a separate expiry or review-due report rather
  than overloading this write receipt.
- If clients add batch suppression, each finding should receive an independent
  receipt with partial-failure reporting.

## Dependencies

- ADR 0001 defines review and conflict workflows.
- ADR 0027 defines review modes and keeps suppression approval human-gated.
- `scripts/review_memory.py` remains the shared source of false-positive review
  state.
