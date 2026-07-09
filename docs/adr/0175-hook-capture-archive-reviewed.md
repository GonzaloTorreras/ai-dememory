# ADR 0175: Hook Capture Archive Reviewed

## Status

Accepted

## Context

Hook capture review now supports bounded summaries, reports, filters, CLI review
receipts, and MCP review receipts. Resolved captures remain in
`inbox/session-events/`, which keeps them out of due counts but can still make
the inbox noisy and slower to scan over time.

Archival must be explicit and reviewed. Hook captures may contain raw payload
bodies if a user opted into raw capture, so selection must rely on frontmatter
only and the command must not inspect payload bodies.

## Decision

Add CLI command `ai-dememory hooks archive`.

By default, the command previews eligible reviewed captures and writes no files.
It moves files only when `--apply` is passed. Eligible captures must:

- live under `inbox/session-events/`;
- have a resolved review status: `reviewed`, `rejected`, or `dismissed`;
- match any provider, event, or review-status filters; and
- satisfy `--min-reviewed-days`.

Applied archives move files to `archive/session-events/` by default. The archive
root is path-bounded to that folder. Destination collisions are skipped instead
of overwritten.

The structured result includes dry-run/write flags, filters, archive root,
eligible and archived counts, bounded candidates, skipped items, malformed
frontmatter candidates, `reads_raw_payloads=false`, and
`canonical_memory_updated=false`.

## Benefits

- Reviewers can keep `inbox/session-events/` focused on unresolved hook
  captures.
- Weekly cleanup has a reviewed manual command before any future maintenance
  automation is considered.
- Raw hook payload bodies are moved only as whole files; they are not read for
  selection or report rendering.
- Destination collision skips avoid accidental overwrites.

## Limitations

- Archival is CLI-only; MCP can review captures but does not move files.
- The command does not delete captures.
- The command does not promote hook content into canonical memory.
- Weekly maintenance does not call archival automatically in this decision.

## Future Risks

- Very large archives may need date-partitioned folders or index pruning.
- If teams want automatic weekly archival, that should be a separate opt-in
  maintenance decision with its own dry-run evidence.

## Dependencies

- ADR 0172 defines hook capture review lifecycle statuses.
- ADR 0173 defines MCP hook capture review receipts.
- ADR 0174 defines hook capture review filters.
- `scripts/hook_event.py` owns CLI archival and path bounds.
