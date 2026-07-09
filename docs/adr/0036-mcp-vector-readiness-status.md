# ADR 0036: MCP Vector Readiness Status

## Status

Accepted for v2 draft.

## Context

ADR 0009 introduced `ai-dememory vector status` as the measured gate for any
future vector-search experiment. That CLI gate keeps SQLite FTS as the default
until recall fixtures show enough failures to justify adding embeddings,
privacy review, and new generated vector artifacts.

After ADR 0035, MCP clients can inspect recall fixture freshness, but they still
cannot inspect the vector-readiness decision directly. That leaves Codex plugin
skills and MCP clients able to see fixture provenance but not the related
decision about whether vector search is justified.

## Decision

Expose `memory.vector_status` as a read-only MCP tool.

The tool calls the same readiness evaluator as `ai-dememory vector status` and
returns:

- decision
- rationale
- recall threshold
- minimum failed case threshold
- recall summary
- failed fixture ids
- generation timestamp

The tool accepts bounded `recall_threshold` and `min_failed_cases` arguments.
It does not write reports, create embeddings, create vector indexes, or enable
vector search.

## Benefits

- Lets MCP clients explain why vector search remains deferred.
- Keeps plugin skills aligned with the same measured gate used by the CLI.
- Makes the vector gate visible in runtime smoke without adding vector
  dependencies.
- Preserves SQLite FTS as the default until measured recall failures justify a
  separate experiment.

## Limitations

- The tool does not estimate whether vectors would fix a failed fixture.
- It does not compare embedding providers, dimensions, costs, or privacy
  boundaries.
- It depends on the current recall fixture set; weak fixtures produce weak
  vector-readiness evidence.

## Future Risks

- If vector experiments are approved later, the MCP output may need backend
  comparison fields.
- Clients may misread `eligible_for_vector_experiment` as approval to implement
  vectors, so docs must keep the explicit user-approval boundary.
- If recall evaluation becomes backend-specific, the vector gate must separate
  FTS baseline results from experimental vector results.

## Dependencies

- Depends on ADR 0009 for the measured vector-search gate.
- Depends on ADR 0035 for the MCP quality-status pattern.
- Depends on `quality/recall-fixtures.json` and `eval-recall` remaining the
  measured source for recall failures.
