# ADR 0201: Review Recommendation Recursive Archive Partitions

Status: Accepted

## Context

ADR 0196 through ADR 0200 added advisory recommendation archival, archive
status, restore, and MCP read-only archive views. Those commands and MCP tools
initially scanned only the selected archive directory. That was sufficient for a
flat `archive/review-recommendations/` folder, but retention workflows may later
group archived artifacts by date or project, such as
`archive/review-recommendations/2026/06/`.

Reviewers need a way to inspect and plan restores from partitioned archives
without weakening the existing archive-root boundary.

## Decision

Add explicit recursive archive scanning for review recommendation archive status
and restore planning.

CLI additions:

- `ai-dememory review recommendations-archive-status --recursive`
- `ai-dememory review recommendations-archive-restore --id <rec_id>
  --recursive`

MCP additions:

- `memory.review_recommendation_archive_status` accepts `recursive=true`;
- `memory.review_recommendation_archive_restore_preview` accepts
  `recursive=true`.

Recursive scans still require `archive_root` to stay under
`archive/review-recommendations/`. The default remains non-recursive so existing
flat archive behavior and bounded review assumptions are preserved. Restore
apply remains CLI-only.

## Benefits

- Date or project partitioned archive directories become inspectable.
- Restore previews can find archived recommendation artifacts in nested
  partitions before a human runs CLI apply.
- The same parser, path guard, and side-effect flags remain in use.
- Existing flat archive workflows are unchanged by default.

## Limitations

- Archive writes still place files in the selected archive root and do not choose
  partitions automatically.
- Recursive scans are bounded by the selected archive tree and can be paged with
  ADR 0202 offset pagination.
- Restore apply still moves restored artifacts back to the flat active inbox.

## Future Work

- Add retention policy helpers if the project needs automatic date/project
  archive destinations.
- Add stable cursor tokens only if offset pagination proves insufficient.

## Dependencies

- ADR 0196 defines CLI archival for reviewed recommendation artifacts.
- ADR 0197 defines CLI archive status.
- ADR 0198 defines CLI archive restore.
- ADR 0199 defines MCP restore preview.
- ADR 0200 defines MCP archive status.
- ADR 0202 defines archive status pagination.
- `scripts/review_memory.py` owns archive scanning and path guards.
- `mcp/server/memory_mcp.py` exposes recursive read-only MCP options.
- `scripts/mcp_runtime_smoke.py` verifies MCP defaults remain non-recursive.
