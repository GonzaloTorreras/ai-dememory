# ADR 0132: Recall Review Candidate Guidance

## Status

Accepted.

## Context

ADR 0130 added `ai-dememory recall-fixtures check-miss`, and ADR 0131 exposed
the same read-only rank check over MCP. Release evidence and recall review
plans still told reviewers to capture a real miss without first surfacing the
safer pre-capture step.

That wording made the final recall-quality blocker less actionable than the
available tooling. Reviewers need a concrete command template in the same
handoff artifact that reports the blocker.

## Decision

Add `candidate_check_command` to the recall review plan.

The field is a read-only command array:

```bash
ai-dememory recall-fixtures check-miss --query <query> --expected-id <memory-id> --json
```

It appears in:

- `ai-dememory recall-fixtures review-plan --json`
- generated `reports/recall-review-plan.md`
- MCP `memory.recall_review_plan`
- `ai-dememory release-evidence --json`

The freshness next action now instructs reviewers to run `check-miss` before
capturing, reviewing, and promoting a real miss.

## Benefits

- Makes the recall-quality release blocker directly actionable.
- Encourages rank verification before writing `inbox/recall-feedback/` files.
- Keeps CLI, MCP, generated report, and release evidence guidance aligned.
- Gives automation a stable command array to render in setup or review UIs.

## Limitations

- The command is a template; reviewers must supply a real query and expected
  memory id or path from actual retrieval behavior.
- It does not satisfy recall freshness by itself.
- It does not identify real misses automatically.

## Future Risks

- If `check-miss` grows more target options, the template should stay generic
  enough for both `expected_id` and `expected_path` workflows.
- If release evidence moves to an external dashboard, the dashboard should
  preserve this pre-capture step.
- If vector search is added later, guidance may need to mention the retrieval
  backend used for the candidate check.

## Dependencies

- ADR 0130 defines the CLI candidate checker.
- ADR 0131 defines the MCP candidate checker.
- ADR 0111 embeds recall review planning in release evidence.
- `scripts/recall_fixtures.py` owns recall review plan rendering and JSON.
- `mcp/server/memory_mcp.py` owns the MCP review-plan schema.
