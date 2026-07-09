# ADR 0216: MCP Recall Review Packet Archive Status

Status: Accepted

## Context

ADR 0214 added CLI archive status for generated recall review packet snapshots.
Local MCP clients can render the current recall review packet with
`memory.recall_review_packet`, but they cannot inspect generated historical
snapshots without invoking the CLI separately.

Recall packet archives are generated guidance, not reviewed recall fixture
promotion evidence. MCP exposure must keep the same read-only boundary as the
CLI status command and must not write reports, fixtures, or miss outcomes.

## Decision

Expose read-only MCP tool `memory.recall_review_packet_archive_status`.

The tool reuses `recall_review_packet_archive_status` and accepts:

- `archive_dir`, optional and still bounded under
  `reports/recall-review-packets/`
- `limit`, capped by the MCP tool page limit
- `offset`

The response mirrors the CLI payload, including archive path, total count,
pagination metadata, archive entries, and side-effect flags:
`writes_files=false`, `records_fixture_promotions=false`,
`writes_fixture_file=false`, and `closes_miss_files=false`.

## Benefits

- MCP clients can inspect generated recall packet snapshot history without
  shelling out to the CLI.
- The CLI and MCP surfaces share the same path guard and pagination behavior.
- Side-effect flags keep generated review packet archives distinct from recall
  quality evidence.

## Limitations

- The tool lists generated Markdown files but does not validate their content.
- The tool does not write archives; archive creation remains a CLI-only action.
- It does not recurse into custom partitions.

## Future Work

- ADR 0218 adds read-only retention planning for generated packet archives.
- Add explicit deletion only if cleanup volume justifies an approval-gated
  apply path.
- Consider a common generated packet archive helper if more packet types need
  the same behavior.

## Dependencies

- ADR 0214 defines CLI recall review packet archive status.
- ADR 0218 defines generated packet archive retention plans.
- `scripts/recall_fixtures.py` owns archive status behavior.
- `mcp/server/memory_mcp.py` exposes the read-only MCP wrapper.
- `scripts/mcp_runtime_smoke.py` verifies the MCP side-effect flags.
