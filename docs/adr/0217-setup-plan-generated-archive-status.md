# ADR 0217: Setup Plan Generated Archive Status

Status: Accepted

## Context

The setup plan already exposes a `generated_reports` command group for optional
review and release handoff files. Later ADRs added timestamped manual
acceptance and recall review packet archives plus read-only archive status
commands.

First-run users and MCP clients now need a discoverable way to inspect generated
packet archive history, but archive status commands must not be confused with
commands that write reports.

## Decision

Add a separate `generated_archive_status` command group to
`ai-dememory setup plan --json` and MCP `memory.setup_plan`.

The group contains command arrays for:

- `recall-fixtures packet-archive-status --json`
- `acceptance packet-archive-status --json`

The setup plan also exposes `suggests_generated_archive_status=true`.

## Benefits

- Makes generated packet archive inspection discoverable during first-run setup.
- Keeps read-only archive inspection separate from generated report writing.
- Allows MCP clients and plugin skills to present archive status commands
  without hard-coding CLI names.

## Limitations

- The setup plan only suggests archive status commands; it does not inspect
  archive directories or create archives.
- Archive status commands may return empty results on fresh vaults.
- Retention preview command discovery is handled separately by ADR 0219.

## Future Risks

- If archive status commands gain required options, setup-plan command arrays
  must stay in sync.
- If generated archive paths move outside `reports/`, install and release docs
  must be updated together.

## Dependencies

- ADR 0117 defines setup-plan generated report commands.
- ADR 0213 defines manual acceptance packet archive status.
- ADR 0214 defines recall review packet archive status.
- ADR 0215 and ADR 0216 expose matching MCP archive status tools.
- ADR 0219 defines setup-plan generated archive retention command discovery.
- `scripts/setup_plan.py` owns the setup-plan command schema.
- MCP `memory.setup_plan` returns the same setup-plan payload.
