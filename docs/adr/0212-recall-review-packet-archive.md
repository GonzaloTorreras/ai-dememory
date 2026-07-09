# ADR 0212: Recall Review Packet Archive

Status: Accepted

## Context

ADR 0187 added generated recall review packets, ADR 0207 added pagination, and
ADR 0210 added optional reviewer and PR URL metadata. The default packet path is
stable so reviewers can regenerate the latest weekly handoff at
`reports/recall-review-packet.md`.

Weekly recall review may still need historical snapshots, especially when a
quality review spans multiple PR iterations. Manually copying generated packets
is easy to forget and can lose reviewer or PR context. At the same time,
archives must remain generated guidance, not fixture promotion evidence.

## Decision

Add CLI-only timestamped recall review packet archives:

- `ai-dememory recall-fixtures packet --archive`
- `ai-dememory recall-fixtures packet --write-report --archive`

The archive writer stores a rendered packet copy under
`reports/recall-review-packets/` with a UTC timestamped filename. If a file
with the same timestamp already exists, the writer appends a numeric suffix.
Custom archive directories are allowed only under `reports/recall-review-packets/`.

The archived packet uses the same renderer as the default report and is
secret-scanned before writing. JSON output reports `writes_archive` and
`archive_path` separately from the stable `report_path`.

MCP `memory.recall_review_packet` remains read-only and does not write archives.

## Benefits

- Weekly quality reviews can retain immutable local packet snapshots without
  manual copying.
- The stable packet report path remains useful for latest-handoff workflows.
- Archive paths stay under a predictable generated reports subtree.

## Limitations

- Archives are generated artifacts, not reviewed fixture promotion evidence.
- Timestamps are local generation time, not proof that a reviewer promoted or
  rejected misses.
- Archive files are not automatically pruned.

## Future Work

- ADR 0214 adds CLI archive status for listing historical recall packet
  snapshots.
- Add retention controls if generated recall packet archives become large.
- Consider a common generated packet archive helper if more packet types need
  the same behavior.

## Dependencies

- ADR 0187 defines the generated recall review packet.
- ADR 0207 defines recall review packet pagination.
- ADR 0210 defines optional recall review packet metadata.
- ADR 0214 defines recall review packet archive status.
- `scripts/recall_fixtures.py` owns recall review packet rendering, writing,
  archiving, and secret scanning.
