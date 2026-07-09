# ADR 0162: Review Enabled Policy Enforcement

Status: Accepted

## Context

ADR 0161 added explicit `[false_positives].enabled` and `[conflicts].enabled`
policy defaults and surfaced them through CLI and MCP review mode/plan output.
Those fields were only guidance, which meant a vault could declare a review
workflow disabled while the corresponding list, report, and write commands still
operated.

The safest first enforcement step is to honor the enabled switches without
introducing automatic cleanup or changing canonical memory behavior.

## Decision

Honor review enabled policy at the review workflow boundary:

- When `[false_positives].enabled = false`, false-positive listing/report tools
  return no candidates.
- False-positive suppress/unignore commands fail before writing review state
  when false-positive review is disabled.
- When `[conflicts].enabled = false`, conflict listing/report tools return no
  candidates.
- Conflict dismiss, keep, and merge-proposal commands fail before writing
  review state or inbox proposal files when conflict review is disabled.

This applies to both CLI and MCP because both surfaces use the same
`scripts/review_memory.py` functions.

## Benefits

- Vault policy now matches observable review workflow behavior.
- Disabled workflows are quiet for read/report operations and explicit for
  write operations.
- Canonical memory remains unchanged; disabled policy cannot accidentally create
  suppressions, conflict decisions, or merge proposals.
- MCP clients can rely on empty candidate lists to mean the workflow is disabled
  or has no candidates, then inspect `memory.review_modes` / `memory.review_plan`
  policy for the distinction.

## Limitations

- `scan_on_validate` and `scan_on_consolidate` remain reported policy values and
  are not enforced by validation or consolidation yet.
- Empty read results do not include a dedicated `disabled` flag in existing
  list responses; callers should inspect review policy output when that
  distinction matters.
- Existing review state files are not migrated or deleted when a workflow is
  disabled.

## Future Work

- Add explicit disabled metadata to review list responses if client UX needs to
  distinguish disabled workflows from empty candidate sets without a second
  policy call.
- Wire `scan_on_validate` into validation once conflict scan failures have a
  stable severity policy.
- Wire `scan_on_consolidate` into consolidation planning without mutating
  canonical memory.

## Dependencies

- ADR 0161 defines review policy defaults and policy output.
- ADR 0160 defines configured review state paths.
- ADR 0149 defines stale false-positive suppression audits.
- ADR 0157 defines conflict categories.
- `scripts/review_memory.py` owns review listing and review-state mutations.
