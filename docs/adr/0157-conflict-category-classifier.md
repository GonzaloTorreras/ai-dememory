# ADR 0157: Conflict Category Classifier

Status: Accepted

## Context

The v2 review plan describes duplicate, stale/current, preference, project
decision, tool policy, and restricted conflict categories. The implemented
scanner already detected duplicate title and alias keys, but it only classified
duplicates as `duplicate`, `preference_conflict`, `project_decision_conflict`,
or `restricted_conflict`.

That made stale/current review and tool-policy precedence less visible in
generated reports, maintenance summaries, and MCP review tools.

## Decision

Extend conflict classification with two categories:

- `stale_vs_current`
- `tool_policy_conflict`

The classifier keeps `restricted_conflict` as the highest-priority category.
After that, active/stale duplicate pairs become `stale_vs_current`. Tool
memories with a policy marker in tags, title, or aliases become
`tool_policy_conflict`.

The scanner still only compares deterministic title and alias keys. It does not
perform semantic contradiction detection.

## Benefits

- Reviewers can distinguish ordinary duplicates from stale/current cleanup.
- Tool policy conflicts get a more cautious suggested action before canonical
  policy changes.
- Maintenance and MCP summaries can count these categories without changing the
  review state format.

## Limitations

- `archived`, `superseded`, and `expired` memories remain excluded from active
  conflict scans.
- `stale_vs_current` only covers explicit `status: stale` paired with
  `status: active`.
- Tool policy detection is marker-based, not semantic.

## Future Work

- Add semantic stale/current and contradiction detection behind a reviewed,
  local-first workflow.
- Add conflict due dates if reviewed decisions need periodic revalidation.
- Consider category-specific MCP prompts once real review usage shows common
  paths.

## Dependencies

- ADR 0001 defines review and conflict workflows.
- ADR 0152 surfaces conflict-review summaries in maintenance status.
- `scripts/review_memory.py` owns deterministic conflict classification.
