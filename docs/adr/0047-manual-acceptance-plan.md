# ADR 0047: Manual Acceptance Plan

## Status

Accepted for the v2 draft.

## Context

Manual acceptance is the final boundary before v2 release readiness. The tool
already records reviewed evidence with `ai-dememory acceptance record`, reports
evidence with `acceptance status`, and fails incomplete releases with
`acceptance verify`. Reviewers still had to mentally translate remaining and
blocked items into the exact commands needed to record passing or blocked
evidence.

That increases friction for the manual checks that intentionally cannot be
automated, such as real MCP client usage, Obsidian inspection, provider import
review, and TestPyPI publishing.

## Decision

Add `ai-dememory acceptance plan`.

The command is read-only. It summarizes completed, remaining, and blocked
manual acceptance items and prints example `acceptance record` commands for
remaining work. JSON output exposes the same plan for release handoffs and local
automation.

The command does not record evidence, run external tools, change acceptance
state, or treat blocked evidence as complete.

## Benefits

- Gives reviewers an actionable checklist for the manual release boundary.
- Keeps evidence recording explicit and separate from planning.
- Makes blocked checks easier to revisit without losing the final passing
  evidence requirement.
- Extends package install smoke to cover the acceptance planning surface.

## Limitations

- The command cannot prove that a manual check was performed.
- Example commands contain placeholders that reviewers must replace with real
  reviewed evidence and artifacts.
- It still trusts existing reviewed Markdown evidence when summarizing current
  state.

## Future Risks

- If acceptance items gain per-item evidence schemas, the generic example
  commands may need item-specific instructions.
- If reviewer identity requirements become stronger, the plan should reference
  the approved identity source.
- If manual acceptance moves outside Markdown, this planner should become a
  client of that external evidence store rather than parsing local records.

## Dependencies

- ADR 0016 defines manual acceptance evidence records.
- ADR 0029 defines the final manual acceptance verification gate.
- ADR 0033 defines release evidence readiness summaries.
