# ADR 0242: Acceptance Plan And Template Metadata

Status: Accepted.

## Context

Manual v2 release acceptance is still the main release blocker after automated
checks pass. Generated manual acceptance packets already accept reviewer and PR
URL metadata so handoff packets can point back to the review context. The
lighter `acceptance plan` and per-item `acceptance template` surfaces still
emitted placeholder `acceptance record` commands, which made reviewers hand-edit
the same reviewer and PR URL into every command.

## Decision

Add optional reviewer and PR URL metadata to:

- `ai-dememory acceptance plan --reviewer ... --pr-url ...`
- `ai-dememory acceptance template --item ... --reviewer ... --pr-url ...`
- MCP `memory.acceptance_plan`
- MCP `memory.acceptance_template`

The metadata pre-fills generated `ai-dememory acceptance record` commands:

- `--reviewed-by` uses the provided reviewer when present.
- `--artifact` uses the provided PR URL when present.

The commands still keep the summary placeholder because each acceptance item
needs item-specific reviewed evidence. These surfaces remain read-only: they do
not write reports, record evidence, publish packages, install schedules, or mark
acceptance complete.

## Benefits

- Reduces repetitive manual editing during release acceptance reviews.
- Keeps CLI and MCP review planning surfaces aligned with packet metadata.
- Makes PR-tied acceptance evidence easier to record consistently.
- Preserves the human review boundary because generated commands still require a
  reviewer to fill item-specific evidence summaries before running them.

## Limitations

- The PR URL is only an artifact hint; it is not proof that the manual check
  passed.
- The feature does not verify reviewer identity.
- The summary remains a placeholder by design.
- Existing generated reports and packets are not backfilled.

## Future Risks

- If acceptance evidence gains signed reviewer attestations, these metadata
  fields should feed that stronger record format instead of plain command
  strings.
- If more artifact types are added, the command generator may need multiple
  prefilled `--artifact` values rather than only the PR URL.
- Shell quoting remains guidance for generated commands; reviewers should still
  inspect unusual reviewer names or artifact values before execution.

## Dependencies

- ADR 0186 defines generated manual acceptance packets.
- ADR 0209 defines manual acceptance packet reviewer and PR URL metadata.
- ADR 0235 defines release evidence handoff commands.
- ADR 0244 hardens generated acceptance command argument quoting.
- `scripts/manual_acceptance.py` owns CLI plan/template rendering.
- `mcp/server/memory_mcp.py` owns MCP acceptance plan/template exposure.
