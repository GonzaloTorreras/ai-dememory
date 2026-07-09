# ADR 0083: MCP Conflict Dismiss Receipts

## Status

Accepted.

## Context

The conflict review workflow supports three reviewed outcomes: dismiss an
intentional conflict, write a merge proposal, or record a keep decision. MCP
already exposed `memory.conflict_dismiss`, but it returned only the updated
ignore-file path. That made it weaker than `memory.conflict_keep` and the
false-positive receipt tools, which return structured audit details.

MCP clients need to know which conflict was dismissed, what status was written,
which decision text was recorded, who reviewed it, and whether canonical memory
was changed.

## Decision

Return a structured receipt from `memory.conflict_dismiss`.

The receipt includes:

- `path`
- `id`
- `status`
- `decision`
- `reviewer`
- `reviewed_at`
- `canonical_memory_updated`

The tool continues to write only `.ai-dememory-ignore.toml`.
`canonical_memory_updated` is always `false` because dismissing a conflict does
not edit, delete, promote, supersede, or rewrite Markdown memory.

## Benefits

- Makes conflict dismiss auditable through MCP without parsing TOML.
- Aligns conflict dismiss with keep decisions and false-positive receipts.
- Lets runtime smoke prove the canonical-memory boundary for every conflict
  write path.

## Limitations

- The receipt records the reviewed dismissal state; it does not prove the
  conflict was semantically safe to dismiss.
- If conflict detection rules change, older conflict ids may no longer map to
  current findings.
- The decision text is reviewer supplied and must remain secret-scanned before
  writing.

## Future Risks

- Batch conflict dismissal should return one receipt per conflict with
  partial-failure reporting.
- If conflict state moves out of `.ai-dememory-ignore.toml`, the receipt should
  remain stable or gain a version field.
- If MCP clients make dismissal too easy, they should show source memory ids and
  summaries before invoking the write tool.

## Dependencies

- ADR 0001 defines review and conflict workflows.
- ADR 0064 defines structured MCP keep-decision receipts.
- `scripts/review_memory.py` remains the source of conflict review state.
