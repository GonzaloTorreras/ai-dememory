# ADR 0223: Release Evidence Next Actions

Status: Accepted

## Context

Release evidence now combines automated checks, structured blockers, manual
acceptance plans, recall quality state, vector readiness, setup health, and
maintenance summaries. Reviewers can find the needed follow-up work in those
sections, but the work is spread across multiple objects and Markdown sections.

Final v2 handoffs need a short ordered list that tells a reviewer what to do
next without replacing the underlying structured evidence.

## Decision

Add a top-level `next_actions` list to release evidence and render it as a
`## Next Actions` section in the Markdown report.

The list is built from existing read-only evidence:

- structured release blocker ids;
- manual acceptance plan next actions;
- recall review plan next actions;
- vector readiness next actions;
- setup health next actions; and
- maintenance summary signals for generated packet archives and pending
  advisory recommendations.

Actions are deduplicated in order and bounded. They do not run commands, write
files, delete generated archives, apply review decisions, record acceptance
evidence, or change canonical memory.

## Benefits

- Release reviewers get one concise handoff list before reading detailed
  evidence sections.
- Manual acceptance, recall review, vector review, setup, and maintenance work
  remain traceable to their source objects.
- MCP clients can display a practical next-step list without parsing Markdown.

## Limitations

- The list is a summary and does not replace `release_blockers`,
  `manual_acceptance_plan`, `recall_fixture_review_plan`, `vector_readiness`,
  `setup_health_summary`, or `maintenance_summary`.
- The order is heuristic and prioritizes blocker-derived work before advisory
  setup and maintenance guidance.
- Manual release decisions remain outside the tool; publish and merge actions
  still require explicit human approval.

## Future Risks

- If the release evidence surface grows further, the bounded list may need
  category labels or pagination.
- If some maintenance signals become release-blocking, they should be promoted
  to explicit `release_blockers` rather than inferred from `next_actions`.
- If remote release dashboards consume the JSON, they should treat
  `next_actions` as guidance and preserve the source evidence objects.

## Dependencies

- ADR 0050 defines structured release blockers.
- ADR 0111 defines recall review plans in release evidence.
- ADR 0184 defines vector readiness in release evidence.
- ADR 0185 defines setup health summaries in release evidence.
- ADR 0222 defines maintenance summaries in release evidence.
- `scripts/release_evidence.py` owns release evidence JSON and Markdown.
