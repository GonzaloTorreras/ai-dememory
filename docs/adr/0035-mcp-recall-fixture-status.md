# ADR 0035: MCP Recall Fixture Status

## Status

Accepted for v2 draft.

## Context

ADR 0034 added `ai-dememory recall-fixtures status` so operators can see
whether recall fixtures are seed-only, stale, or fresh based on reviewed miss
promotions. That solved the CLI and scheduled-review workflow, but MCP clients
and Codex plugin skills still needed to shell out to inspect the same quality
state.

The v2 MCP surface already exposes read-only release readiness, maintenance,
review, and schedule planning helpers. Recall fixture freshness is similar:
clients need visibility, but they must not mutate the curated fixture file or
promote synthetic data as if it came from a reviewed miss.

## Decision

Expose `memory.recall_fixture_status` as a read-only MCP tool.

The tool returns the same structured freshness fields as the CLI status command:

- fixture file path
- total fixture count
- reviewed promotion count
- seed fixture count
- latest `created_at` and `reviewed_at`
- days since latest reviewed promotion
- stale and missing-reviewed-promotion booleans
- status and next action text

The only input is `max_age_days`, clamped between 1 and 365. The tool does not
write to `quality/recall-fixtures.json`, does not promote misses, and does not
record release acceptance evidence.

## Benefits

- Lets MCP clients report recall-quality freshness without launching a shell.
- Keeps plugin skills aligned with the same quality status used by CLI review
  jobs.
- Makes seed-only fixture sets visible during MCP runtime smoke.
- Preserves the reviewed-promotion boundary for fixture changes.

## Limitations

- The tool reports fixture freshness, not retrieval pass/fail; `eval-recall`
  remains the recall correctness gate.
- Freshness does not prove that promoted misses are representative.
- The tool cannot capture or promote misses; those remain explicit CLI or inbox
  review workflows.

## Future Risks

- If fixture metadata gains categories or owners, the MCP output schema may need
  per-category freshness summaries.
- MCP clients may present stale status as a release blocker even though v2 keeps
  it advisory until manual review records real miss promotion.
- If recall fixtures move out of JSON, both the CLI and MCP tool need a shared
  loader update.

## Dependencies

- Depends on ADR 0017 for reviewed recall miss promotion.
- Depends on ADR 0034 for the shared freshness status model.
- Depends on `mcp-inventory --check-docs` and MCP runtime smoke coverage to
  keep the documented tool surface in sync.
