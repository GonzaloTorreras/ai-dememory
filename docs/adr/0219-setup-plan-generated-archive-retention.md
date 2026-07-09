# ADR 0219: Setup Plan Generated Archive Retention

Status: Accepted

## Context

ADR 0218 added read-only retention plans for generated manual acceptance and
recall review packet archives. ADR 0217 already made archive status commands
discoverable in `ai-dememory setup plan --json` and MCP `memory.setup_plan`,
but retention plans remained discoverable only by reading command docs.

First-run users and MCP/plugin setup flows need the same command-array
discovery for retention previews. The setup plan must still remain passive: it
must not inspect archive directories, choose files to delete, or run retention
logic.

## Decision

Add a separate `generated_archive_retention` command group to
`ai-dememory setup plan --json` and MCP `memory.setup_plan`.

The group contains command arrays for:

- `recall-fixtures packet-archive-retention-plan --json`
- `acceptance packet-archive-retention-plan --json`

The setup plan also exposes `suggests_generated_archive_retention=true`.

## Benefits

- Makes generated packet retention previews discoverable during first-run setup.
- Keeps retention preview commands separate from archive status browsing and
  generated report writing.
- Allows MCP clients and plugin skills to present cleanup preview commands
  without hard-coding CLI names.

## Limitations

- The setup plan only suggests retention preview commands; it does not inspect
  archives, compute candidates, or delete files.
- Fresh vaults may return empty retention plans because no generated packet
  archives exist yet.
- Approval-gated deletion remains out of scope.

## Future Risks

- If retention plans gain required policy or keep-count options, setup-plan
  command arrays must stay in sync.
- If deletion support is added later, it must not be exposed as a passive
  setup-plan default command.

## Dependencies

- ADR 0079 defines the local setup planner.
- ADR 0217 defines setup-plan generated archive status commands.
- ADR 0218 defines generated packet archive retention plans.
- `scripts/setup_plan.py` owns the setup-plan command schema.
- MCP `memory.setup_plan` returns the same setup-plan payload.
