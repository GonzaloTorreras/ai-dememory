# ADR 0049: Release Evidence Acceptance Plan

Status: Accepted for the v2 draft.

## Context

`ai-dememory release-evidence` is the final local handoff artifact for v2
readiness. It already reports automated checks, MCP inventory, publish guard
state, completed manual acceptance items, blocked items, and remaining manual
acceptance descriptions.

ADR 0047 added `ai-dememory acceptance plan`, and ADR 0048 exposed that same
plan through MCP. Release handoffs still required a second command to see the
next actions and example evidence-record commands. That made strict release
evidence less actionable when it failed because manual acceptance was
incomplete.

## Decision

Embed the shared acceptance planner output in release evidence as
`manual_acceptance_plan`.

The JSON output includes the complete planner dictionary. The Markdown report
renders a `Manual Acceptance Plan` section with remaining or blocked item ids,
next actions, and example passing or blocked `ai-dememory acceptance record`
commands.

Release evidence remains read-only. It does not record manual evidence, mark
items complete, or promote any inbox candidate.

## Benefits

- Makes strict release-evidence failures actionable without a second command.
- Gives PR comments and release handoffs the exact reviewed commands needed to
  finish manual acceptance.
- Reuses the canonical planner instead of maintaining a separate checklist
  formatter.

## Limitations

- Command examples are guidance, not proof that a reviewer performed the manual
  acceptance check.
- The plan can become stale after new acceptance records are added.
- Markdown command rendering is intended for humans; automation should consume
  the JSON `manual_acceptance_plan` field.

## Future Risks

- If manual acceptance moves outside Markdown records, release evidence must
  follow the same planner backend as the CLI and MCP tools.
- If reviewer identity requirements become stronger, command examples may need
  structured identity fields instead of placeholder text.
- If external CI state becomes part of release evidence, the manual plan should
  remain separate from automated readiness signals.

## Dependencies

- ADR 0033 defines release evidence readiness summaries.
- ADR 0047 defines the shared CLI manual acceptance planner.
- ADR 0048 exposes the same planner through MCP.
- `scripts/release_evidence.py` depends on `scripts/manual_acceptance.py` for
  the canonical plan shape.
