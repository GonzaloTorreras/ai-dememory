# ADR 0196: Review Recommendation Archive

Status: Accepted

## Context

ADR 0188 introduced advisory review recommendation artifacts under
`inbox/review-recommendations/`. ADR 0191 added accepted/rejected outcome
status, and ADR 0195 made pending and reviewed recommendation counts visible in
maintenance status and setup health.

Reviewed recommendations still remained in the active inbox indefinitely. That
kept stale advisory artifacts mixed with pending review work and made recurring
maintenance summaries noisier over time.

## Decision

Add CLI command `ai-dememory review recommendations-archive`.

The command previews by default and moves files only when `--apply` is supplied.
It archives accepted/rejected recommendation artifacts from
`inbox/review-recommendations/` to `archive/review-recommendations/`.

Supported filters and guards:

- `--outcome-status reviewed|accepted|rejected`, defaulting to `reviewed`;
- `--min-outcome-days N`, defaulting to `0`;
- `--archive-root`, which must stay under `archive/review-recommendations/`;
- pending recommendations are skipped;
- malformed recommendation artifacts are reported and left in place;
- existing archive paths are skipped instead of overwritten.

The command returns side-effect flags showing that it does not apply review
decisions, write canonical memory, or update durable memory. It is CLI-only for
this slice because it moves files.

## Benefits

- Reviewed advisory recommendations can leave the active inbox without losing
  audit history.
- Maintenance summaries become focused on pending recommendation work.
- Dry-run output supports review before any file move.
- Archive path checks keep file moves inside the memory vault.

## Limitations

- The archive is a file move, not a retention policy engine.
- Archived recommendations are no longer returned by
  `ai-dememory review recommendations`; users inspect the archive directory or
  Git history for older decisions.
- The command does not compress, delete, or expire archived artifacts.
- MCP does not expose an archive writer in this slice.

## Future Work

- Add retention policy configuration if archived recommendation volume becomes
  operationally significant.
- Consider MCP exposure only if a client workflow needs approval-gated archive
  moves.

## Dependencies

- ADR 0188 defines advisory recommendation artifacts.
- ADR 0191 defines accepted/rejected recommendation outcomes.
- ADR 0195 summarizes recommendation queues in maintenance and setup health.
- ADR 0197 defines read-only archive status for archived recommendation
  artifacts.
- `scripts/review_memory.py` owns recommendation artifact parsing and archive
  moves.
- `scripts/install_smoke.py` verifies installed CLI command wiring.
