# ADR 0214: Recall Review Packet Archive Status

Status: Accepted

## Context

ADR 0212 added timestamped recall review packet archives under
`reports/recall-review-packets/`. Those archives keep historical generated
review packets, but reviewers still need a simple way to list existing
snapshots without manually inspecting the reports directory or treating
generated packets as fixture promotion evidence.

## Decision

Add `ai-dememory recall-fixtures packet-archive-status`.

The command is CLI-only for this milestone and returns:

- `archive_root`
- `total_count`
- `limit`, `offset`, `returned_count`, `next_offset`, and `has_more`
- `archives`, each with path, byte size, modified timestamp, and timestamp
  parsed from the generated filename when available
- side-effect flags showing `writes_files=false`,
  `records_fixture_promotions=false`, `writes_fixture_file=false`, and
  `closes_miss_files=false`

The archive directory is bounded under `reports/recall-review-packets/`. The
status command lists only Markdown files directly under that directory, sorted
newest filename first.

## Benefits

- Weekly recall reviewers can inspect available generated packet snapshots from
  the CLI.
- Pagination keeps large local archive directories predictable.
- Side-effect flags preserve the distinction between generated review packets
  and reviewed recall quality evidence.

## Limitations

- Archive status does not validate packet content.
- It does not recurse into custom partitions.
- MCP exposure is deferred until a real client workflow needs archive browsing.

## Future Work

- ADR 0218 adds read-only retention planning for generated packet archives.
- Add explicit deletion only if cleanup volume justifies an approval-gated
  apply path.
- ADR 0216 exposes the same read model over MCP.
- Consider a common generated packet archive helper if more packet types need
  the same behavior.

## Dependencies

- ADR 0212 defines recall review packet archives.
- ADR 0216 defines MCP recall review packet archive status.
- ADR 0218 defines generated packet archive retention plans.
- `scripts/recall_fixtures.py` owns archive path bounds, archive listing, and
  CLI output.
