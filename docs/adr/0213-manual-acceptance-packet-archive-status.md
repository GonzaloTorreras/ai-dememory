# ADR 0213: Manual Acceptance Packet Archive Status

Status: Accepted

## Context

ADR 0211 added timestamped manual acceptance packet archives under
`reports/manual-acceptance-packets/`. That keeps local packet snapshots, but
reviewers still need a low-risk way to list which generated snapshots exist
without reading the filesystem manually or confusing generated packets with
reviewed acceptance evidence.

## Decision

Add `ai-dememory acceptance packet-archive-status`.

The command is CLI-only for this milestone and returns:

- `archive_root`
- `total_count`
- `limit`, `offset`, `returned_count`, `next_offset`, and `has_more`
- `archives`, each with path, byte size, modified timestamp, and timestamp
  parsed from the generated filename when available
- side-effect flags showing `writes_files=false`, `records_evidence=false`,
  and `writes_acceptance_records=false`

The archive directory is still bounded under
`reports/manual-acceptance-packets/`. The status command lists only Markdown
files directly under that directory, sorted newest filename first.

## Benefits

- Release reviewers can inspect available generated packet snapshots from the
  same CLI used to create them.
- Pagination keeps large local archive directories predictable.
- Side-effect flags preserve the distinction between generated reports and
  reviewed acceptance evidence.

## Limitations

- Archive status does not validate packet content.
- It does not recurse into custom partitions.
- MCP exposure is deferred until a real client workflow needs archive browsing.

## Future Work

- ADR 0218 adds read-only retention planning for generated packet archives.
- Add explicit deletion only if cleanup volume justifies an approval-gated
  apply path.
- ADR 0215 exposes the same read model over MCP.
- ADR 0214 adds matching recall review packet archive status.

## Dependencies

- ADR 0211 defines manual acceptance packet archives.
- ADR 0215 defines MCP manual acceptance packet archive status.
- ADR 0218 defines generated packet archive retention plans.
- `scripts/manual_acceptance.py` owns archive path bounds, archive listing, and
  CLI output.
