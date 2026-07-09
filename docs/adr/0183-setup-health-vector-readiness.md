# ADR 0183: Setup Health Vector Readiness

Status: Accepted

## Context

The v2 memory-quality plan keeps SQLite FTS as the default retrieval layer and
defers vector search until recall fixtures show measured failures. ADR 0009
added `ai-dememory vector status`, and ADR 0036 exposed the same measured gate
through MCP `memory.vector_status`.

`setup health` already surfaces recall review state, but setup and plugin flows
still had to call a separate vector tool to see whether the current recall
fixture results justify a future vector experiment.

## Decision

Add a compact `vector_readiness` object to `ai-dememory setup health --json`
and MCP `memory.setup_health`.

When recall fixtures exist, the object reuses `evaluate_vector_readiness` and
reports:

- decision;
- rationale;
- recall thresholds;
- recall summary;
- failed case ids;
- generated timestamp;
- `available=true`;
- `creates_embeddings=false`;
- `mutates_system=false`;
- `runs_commands=false`; and
- `writes_files=false`.

When `quality/recall-fixtures.json` is missing, the object reports
`available=false`, `decision=unavailable`, an error, and a next action to add
recall fixtures first.

## Benefits

- Setup health shows the full memory-quality path: recall review first, then
  measured vector readiness.
- Plugin setup can explain why vector search remains deferred without creating
  embeddings or extra indexes.
- The same readiness logic is shared across CLI, MCP, and setup health.
- Missing fixture state is explicit and actionable.

## Limitations

- Setup health does not write the generated vector-readiness report; users
  should run `ai-dememory vector status --write-report` when they need durable
  evidence.
- The summary does not enable vector search or approve new dependencies.
- A decision of `eligible_for_vector_experiment` is still only a review signal;
  implementation and privacy model approval remain separate work.

## Future Work

- Link setup health to generated vector readiness reports if a stable report
  manifest exists.
- Add provider/privacy diagnostics before any vector implementation is approved.
- Revisit thresholds after real recall fixture volume grows.

## Dependencies

- ADR 0009 defines the measured vector-search gate.
- ADR 0036 exposes vector readiness over MCP.
- ADR 0180 adds recall review state to setup health.
- `scripts/vector_gate.py` owns vector readiness evaluation.
- `scripts/setup_plan.py` owns setup health assembly.
