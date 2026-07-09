# ADR 0215: MCP Manual Acceptance Packet Archive Status

Status: Accepted

## Context

ADR 0213 added CLI archive status for generated manual acceptance packet
snapshots. Local MCP clients can render the current manual acceptance packet
with `memory.acceptance_packet`, but they still cannot inspect which archived
generated packet snapshots exist without invoking the CLI separately.

Generated packet archives are not reviewed acceptance evidence, so exposing
them over MCP must preserve the same read-only boundary as the CLI status
command.

## Decision

Expose read-only MCP tool `memory.acceptance_packet_archive_status`.

The tool reuses `acceptance_packet_archive_status` and accepts:

- `archive_dir`, optional and still bounded under
  `reports/manual-acceptance-packets/`
- `limit`, capped by the MCP tool page limit
- `offset`

The response mirrors the CLI payload, including archive path, total count,
pagination metadata, archive entries, and side-effect flags:
`writes_files=false`, `records_evidence=false`, and
`writes_acceptance_records=false`.

## Benefits

- MCP clients can inspect generated packet snapshot history without shelling out
  to the CLI.
- The CLI and MCP surfaces share the same path guard and pagination behavior.
- Side-effect flags make it clear that archive status is not acceptance
  evidence.

## Limitations

- The tool lists generated Markdown files but does not validate their content.
- The tool does not write archives; archive creation remains a CLI-only action.
- It does not recurse into custom partitions.

## Future Work

- ADR 0218 adds read-only retention planning for generated packet archives.
- Add explicit deletion only if cleanup volume justifies an approval-gated
  apply path.
- Add matching recall review packet archive status over MCP if recall review
  clients need snapshot browsing.

## Dependencies

- ADR 0213 defines CLI manual acceptance packet archive status.
- ADR 0218 defines generated packet archive retention plans.
- `scripts/manual_acceptance.py` owns archive status behavior.
- `mcp/server/memory_mcp.py` exposes the read-only MCP wrapper.
- `scripts/mcp_runtime_smoke.py` verifies the MCP side-effect flags.
