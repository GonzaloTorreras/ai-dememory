# ADR 0040: MCP Doctor Status

## Status

Accepted for the v2 draft.

## Context

`ai-dememory doctor` is the first diagnostic command users run when validating
a vault or the distribution checkout. MCP clients could inspect many individual
readiness signals, but they could not request the same compact doctor result
without shelling out to the CLI.

## Decision

Expose `memory.doctor` as a read-only MCP tool. The tool calls the existing
doctor checks and returns:

- `checks`: the same named status rows as the CLI doctor;
- `summary`: counts for `ok`, `warn`, `fail`, and `total`.

The tool does not write reports, rebuild indexes, install schedules, promote
memory, or record acceptance evidence. It preserves the existing doctor
semantics, including warnings for missing generated indexes.

## Benefits

- Gives MCP clients one simple vault-health check.
- Keeps plugin setup workflows from needing shell access for basic diagnostics.
- Reuses the existing doctor implementation instead of creating parallel checks.

## Limitations

- Doctor output is diagnostic, not a release gate by itself.
- Some checks are most meaningful in the distribution checkout rather than a
  minimal memory vault.
- The tool reports current state only; it does not repair warnings.

## Future Risks

- If doctor checks become slow, MCP clients may need progress or task support.
- Vault and distribution diagnostics are profile-aware as documented by ADR
  0041.
- Clients may treat warnings as fatal unless UI copy preserves the status
  distinction.

## Dependencies

- ADR 0010 keeps MCP inventory drift guarded.
- ADR 0021 requires runtime smoke coverage when new MCP tools are added.
- ADR 0031 requires new ADRs to document tradeoffs and dependencies.
- ADR 0041 refines doctor behavior for vault roots.
