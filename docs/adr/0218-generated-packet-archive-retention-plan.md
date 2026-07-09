# ADR 0218: Generated Packet Archive Retention Plan

Status: Accepted

## Context

Generated manual acceptance and recall review packet archives are useful for
release handoffs and weekly review history, but ADRs 0211 through 0216 left
retention controls as future work. Operators now have archive status commands,
yet they still cannot see which files would be candidates for cleanup without
manually inspecting timestamped report directories.

Automatic deletion would be too risky for this milestone because generated
packets can still be useful audit context. The immediate need is a bounded,
reviewable cleanup plan that keeps generated artifacts separate from reviewed
acceptance evidence and recall fixture promotions.

## Decision

Add read-only generated packet archive retention plans:

- `ai-dememory recall-fixtures packet-archive-retention-plan`
- `ai-dememory acceptance packet-archive-retention-plan`
- MCP `memory.recall_review_packet_archive_retention_plan`
- MCP `memory.acceptance_packet_archive_retention_plan`

Each plan lists `prune_candidates` after retaining the newest `--keep` archive
files. The default keeps the newest 30 files. Results are paginated with
`limit` and `offset`.

The payload includes explicit side-effect flags:

- `mutates_system=false`
- `writes_files=false`
- `deletes_files=false`
- recall-specific fixture and miss outcome flags remain false
- acceptance-specific evidence and acceptance-record flags remain false

## Benefits

- Reviewers can see generated packet cleanup candidates without deleting files.
- The same CLI and MCP contract covers manual acceptance and recall review
  packet archives.
- Pagination keeps large generated archive directories usable in MCP clients.
- Future destructive pruning can reuse the same candidate ordering if it is
  added behind an explicit apply flag.

## Limitations

- The plan does not delete or move files.
- It keeps by newest filename order, matching archive status behavior, rather
  than parsing packet content.
- It does not recurse into custom archive partitions.
- It does not enforce retention during packet creation.

## Future Risks

- If generated packet volume becomes very large, listing direct Markdown files
  may need a faster index or partitioned archive directories.
- If an apply command is added later, it must require explicit user approval,
  path bounds, and a dry-run default.
- Retention defaults may need configuration once real usage shows how many
  packet snapshots reviewers keep.
- Setup-plan command discovery must stay aligned with ADR 0219 if retention
  command names change.

## Dependencies

- ADR 0211 and ADR 0212 define generated packet archives.
- ADR 0213 and ADR 0214 define archive status ordering and pagination.
- ADR 0215 and ADR 0216 expose generated packet archive status through MCP.
- ADR 0219 defines setup-plan command discovery for retention previews.
- `scripts/manual_acceptance.py` owns manual acceptance packet retention plans.
- `scripts/recall_fixtures.py` owns recall review packet retention plans.
- `mcp/server/memory_mcp.py` exposes the read-only MCP retention tools.
