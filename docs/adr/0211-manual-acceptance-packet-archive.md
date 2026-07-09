# ADR 0211: Manual Acceptance Packet Archive

Status: Accepted

## Context

ADR 0186 added generated manual acceptance packets, ADR 0208 added pagination,
and ADR 0209 added optional reviewer and PR URL metadata. The default packet
report path is intentionally stable so release handoffs can overwrite the
latest generated guidance.

Some release reviews still need historical packet snapshots, especially when a
draft PR goes through multiple manual acceptance passes. Requiring reviewers to
copy the generated report manually is error-prone, but packet archives must
remain generated artifacts and must not become acceptance evidence.

## Decision

Add CLI-only timestamped packet archive support:

- `ai-dememory acceptance packet --archive`
- `ai-dememory acceptance packet --write-report --archive`

The archive writer stores a copy of the rendered packet under
`reports/manual-acceptance-packets/` with a UTC timestamped filename. If a file
with the same timestamp already exists, the writer appends a numeric suffix.
Custom archive directories are allowed only under
`reports/manual-acceptance-packets/`.

The archived packet uses the same renderer as the default report and is
secret-scanned before writing. JSON output reports `writes_archive` and
`archive_path` separately from the stable `report_path`.

MCP `memory.acceptance_packet` remains read-only and does not write archives.

## Benefits

- Release reviewers can retain immutable local packet snapshots without
  manually copying generated Markdown.
- The stable packet report path remains useful for "latest handoff" workflows.
- The archive path guard keeps generated packet history under a predictable
  reports subtree.

## Limitations

- Archives are generated artifacts, not reviewed acceptance evidence.
- Timestamps are local generation time, not proof that a reviewer completed the
  manual checks.
- Archive files are not automatically pruned.

## Future Work

- ADR 0213 adds CLI archive status for listing historical packet snapshots.
- Add retention controls if generated packet archives become large.
- ADR 0212 adds matching CLI-only recall review packet archives.

## Dependencies

- ADR 0186 defines the generated manual acceptance packet.
- ADR 0208 defines manual acceptance packet pagination.
- ADR 0209 defines optional manual acceptance packet metadata.
- ADR 0213 defines manual acceptance packet archive status.
- `scripts/manual_acceptance.py` owns manual acceptance packet rendering,
  writing, archiving, and secret scanning.
