# ADR 0025: Blocked Manual Acceptance Evidence

## Status

Accepted for v2 draft.

## Context

Manual release acceptance supports both `passed` and `blocked` records. Before
this ADR, `ai-dememory release-evidence` only separated completed and remaining
items, so a reviewer could not tell whether an item had not been attempted or
had been attempted and blocked by a local setup, provider, or client limitation.

Blocked evidence should be visible without treating the item as release-ready.

## Decision

Extend `ai-dememory release-evidence` to include a
`manual_acceptance_blocked` section in JSON and Markdown output.

Blocked entries include:

- acceptance item id and description
- reviewed record path
- reviewer name
- review date
- summary
- artifact links

Blocked items remain in `manual_acceptance_remaining` until a later `passed`
record exists for the same acceptance item.

## Benefits

- Distinguishes missing manual proof from reviewed blockers.
- Keeps failed or unavailable acceptance attempts auditable.
- Gives PR reviewers enough context to decide whether to retry, defer, or
  adjust the acceptance plan.
- Preserves the existing rule that only reviewed `passed` records complete a
  manual acceptance item.

## Limitations

- Blocked evidence is reviewer-entered and still requires human judgment.
- The report does not retry blocked checks automatically.
- A blocked record can become stale after local setup or external provider
  conditions change.

## Future Risks

- If acceptance blockers become frequent, the release checklist may need a
  dedicated blocker triage workflow.
- If acceptance records need stronger identity guarantees, blocked evidence
  should follow the same provenance upgrade as passed records.
