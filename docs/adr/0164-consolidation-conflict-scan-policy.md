# ADR 0164: Consolidation Conflict Scan Policy

Status: Accepted

## Context

ADR 0161 exposed `[conflicts].scan_on_consolidate`, ADR 0162 enforced the
enabled review workflow boundary, and ADR 0163 wired `scan_on_validate` into the
validation command. Consolidation dry-runs still did not reflect
`scan_on_consolidate`, even though consolidation is one of the main places where
duplicate, stale/current, and policy conflicts are useful review evidence.

The consolidation command must remain review-first and must not mutate canonical
memory or review state.

## Decision

When `[conflicts].enabled = true` and `[conflicts].scan_on_consolidate = true`,
include a non-blocking conflict review scan section in the consolidation dry-run
report. The section records:

- scan status;
- total conflicts;
- active conflicts;
- up to 20 active conflict ids; and
- a message explaining that no memory was mutated.

When conflict review is disabled, the section reports `disabled`. When
`scan_on_consolidate = false`, it reports `skipped`. If policy parsing or
conflict scanning fails, consolidation fails before writing the report.

## Benefits

- Consolidation reports now include the conflict evidence reviewers need before
  merging, superseding, or archiving memories.
- The configured `scan_on_consolidate` policy has observable behavior.
- The report remains generated evidence only; canonical memory and review state
  are untouched.
- MCP `memory.consolidate` inherits the same behavior because it uses the same
  report builder.

## Limitations

- Active conflicts do not block report generation.
- The report includes conflict ids but not full conflict details; reviewers must
  run `ai-dememory review conflicts` for full evidence.
- The scan adds a second validation/conflict pass to consolidation report
  generation.

## Future Work

- Add category/severity policy if some conflict classes should block
  consolidation report generation.
- Link active conflict ids to generated conflict reports when a stable report
  manifest exists.
- Add structured MCP metadata if clients need conflict scan details without
  parsing the Markdown report.

## Dependencies

- ADR 0161 defines review policy defaults.
- ADR 0162 enforces enabled review workflow boundaries.
- ADR 0163 wires scan-on-validate.
- ADR 0157 defines conflict categories.
- `scripts/consolidate_memory.py` owns consolidation report generation.
- `scripts/review_memory.py` owns conflict scanning and policy parsing.
