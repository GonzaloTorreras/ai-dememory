# ADR 0199: MCP Review Recommendation Archive Restore Preview

Status: Accepted

## Context

ADR 0198 added CLI-only restore for one archived advisory recommendation
artifact. The restore command previews by default, but applying it moves a file
from `archive/review-recommendations/` back to
`inbox/review-recommendations/`.

MCP clients benefit from seeing whether a restore is possible before asking a
human to run the CLI command, but exposing the apply operation through MCP would
turn a review-planning surface into a file-move surface.

## Decision

Expose read-only MCP tool
`memory.review_recommendation_archive_restore_preview`.

The tool accepts:

- `id`: required recommendation id;
- `archive_root`: optional archive root that must stay under
  `archive/review-recommendations/`.

It calls the same restore planner as the CLI with `apply=false` and returns the
same structured dry-run payload: candidates, skipped items, malformed artifacts,
archive and inbox roots, and side-effect flags. It always returns
`dry_run=true`, `writes_files=false`, `applies_review_decisions=false`,
`writes_canonical_memory=false`, and `canonical_memory_updated=false`.

The actual restore move remains CLI-only through
`ai-dememory review recommendations-archive-restore --id <rec_id> --apply`.

## Benefits

- MCP clients can show a safe restore plan before a human runs the CLI apply.
- The preview reuses the CLI path guards and destination-overwrite checks.
- The tool keeps the plugin review workflow informed without adding MCP file
  moves.
- Runtime smoke can verify restore planning side-effect flags over stdio.

## Limitations

- MCP cannot apply the restore.
- ADR 0201 adds optional recursive scanning for partitioned archives.
- Clients must still use the CLI to move the artifact after human approval.

## Future Work

- Reconsider MCP apply only if the repository adds a stronger approval receipt
  model for MCP file moves.

## Dependencies

- ADR 0196 defines CLI-only archival for reviewed recommendation artifacts.
- ADR 0197 defines read-only archive status.
- ADR 0198 defines CLI-only archive restore.
- ADR 0201 defines optional recursive archive partition scans.
- `scripts/review_memory.py` owns the restore planner and path guards.
- `mcp/server/memory_mcp.py` exposes the read-only preview tool.
- `scripts/mcp_runtime_smoke.py` verifies preview side-effect flags.
