# ADR 0198: Review Recommendation Archive Restore

Status: Accepted

## Context

ADR 0196 added CLI-only archival for reviewed recommendation artifacts, and ADR
0197 added read-only archive status. Together they keep
`inbox/review-recommendations/` focused on active advisory work while retaining
accepted/rejected recommendation history under `archive/review-recommendations/`.

Reviewers still need a safe way to reopen a single archived recommendation when
an outcome needs follow-up, correction, or additional evidence. Restoring must
not apply the advisory decision or mutate canonical memory.

## Decision

Add CLI command `ai-dememory review recommendations-archive-restore`.

The command requires `--id rec_...`, previews by default, and accepts `--apply`
to move the selected archived Markdown artifact back to
`inbox/review-recommendations/`. It supports `--archive-root` and `--json`.

Restore behavior is intentionally narrow:

- custom archive roots must stay under `archive/review-recommendations/`;
- only archived Markdown artifacts matching the requested recommendation id are
  considered;
- restore refuses to overwrite an existing inbox destination path;
- returned side-effect flags distinguish preview from apply and always report
  `applies_review_decisions=false`, `writes_canonical_memory=false`, and
  `canonical_memory_updated=false`.

## Benefits

- Reviewers can reopen archived advisory artifacts without Git spelunking.
- Archive cleanup remains reversible without applying LLM recommendations.
- Existing archive and archive-status workflows keep their safety boundaries.
- Install smoke can verify restore command wiring without moving files.

## Limitations

- The command restores one recommendation id at a time.
- ADR 0201 adds optional recursive scanning for partitioned archives.
- MCP exposes only the read-only restore preview in ADR 0199; the apply path
  stays CLI-only because restore moves files.

## Future Work

- Reconsider MCP apply only if a stronger approval receipt model for MCP file
  moves is added.

## Dependencies

- ADR 0188 defines advisory recommendation artifacts.
- ADR 0191 defines accepted/rejected recommendation outcomes.
- ADR 0196 defines CLI-only archival for accepted/rejected recommendation
  artifacts.
- ADR 0197 defines read-only archive status.
- ADR 0199 defines MCP restore preview.
- ADR 0201 defines optional recursive archive partition scans.
- `scripts/review_memory.py` owns recommendation artifact parsing, archival,
  archive status, and restore.
- `scripts/install_smoke.py` verifies installed CLI command wiring.
