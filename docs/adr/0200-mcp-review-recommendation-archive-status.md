# ADR 0200: MCP Review Recommendation Archive Status

Status: Accepted

## Context

ADR 0197 added CLI archive status for accepted/rejected advisory
recommendation artifacts. ADR 0199 later exposed MCP restore preview, which lets
clients check whether one archived artifact can be reopened, but clients still
could not inspect archived recommendation history through MCP.

Archive status is read-only and already has path guards, filters, malformed file
reporting, and side-effect flags. Exposing the same model through MCP keeps
review workflows visible without adding file moves.

## Decision

Expose read-only MCP tool `memory.review_recommendation_archive_status`.

The tool accepts:

- `archive_root`, which must stay under `archive/review-recommendations/`;
- optional `kind`;
- optional `outcome_status` of `accepted` or `rejected`;
- bounded `limit`.

It returns the same status payload as
`ai-dememory review recommendations-archive-status --json`: total and returned
counts, accepted/rejected counts, kind counts, malformed artifacts, filtered
recommendation records, and side-effect flags. It always reports
`writes_files=false`, `applies_review_decisions=false`, and
`writes_canonical_memory=false`.

## Benefits

- MCP clients can inspect archived recommendation history without reading files
  by hand.
- Restore-preview workflows can first list archived candidates, then preview a
  selected id.
- Runtime smoke now verifies archive status side-effect flags over stdio.
- The plugin MCP inventory remains aligned with review workflow documentation.

## Limitations

- The tool is read-only and does not restore, archive, delete, or apply
  recommendation outcomes.
- ADR 0201 adds optional recursive scanning for partitioned archives.
- ADR 0202 adds offset pagination for large archive history.

## Future Work

- Add stable cursor tokens only if offset pagination proves insufficient.

## Dependencies

- ADR 0196 defines CLI-only archival for reviewed recommendation artifacts.
- ADR 0197 defines CLI archive status.
- ADR 0198 defines CLI archive restore.
- ADR 0199 defines MCP archive restore preview.
- ADR 0201 defines optional recursive archive partition scans.
- ADR 0202 defines archive status pagination.
- `scripts/review_memory.py` owns archive status parsing and path guards.
- `mcp/server/memory_mcp.py` exposes the read-only archive status tool.
- `scripts/mcp_runtime_smoke.py` verifies archive status side-effect flags.
