# ADR 0184: Release Evidence Vector Readiness

Status: Accepted

## Context

The v2 release handoff already includes automated release checks, manual
acceptance evidence, recall fixture freshness, and the recall review plan.
Vector search remains deferred until recall fixtures show measured failures,
but reviewers still needed a separate `ai-dememory vector status` run to see
that gate in the final release evidence.

ADR 0183 added vector readiness to setup health for first-run and plugin setup
flows. The release handoff needs the same read-only signal so a reviewer can
decide whether SQLite FTS is still sufficient without creating embeddings or
enabling a new retrieval dependency.

## Decision

Add a `vector_readiness` object to `ai-dememory release-evidence --json`, the
Markdown release-evidence report, and MCP `memory.release_evidence`.

The object reuses `evaluate_vector_readiness` and reports the measured decision,
rationale, thresholds, recall summary, failed fixture ids, generated timestamp,
and the read-only flags:

- `available`;
- `creates_embeddings=false`;
- `mutates_system=false`;
- `runs_commands=false`; and
- `writes_files=false`.

If recall fixtures are unavailable or invalid, the object reports
`decision=unavailable`, includes the evaluation error, and gives a next action.
If the generated memory index is missing while fixtures exist, the next action
is to run `ai-dememory index`.

When the decision is `eligible_for_vector_experiment`, release evidence adds a
`vector_readiness_review` quality blocker. The blocker is review-only: it does
not implement vector search, create embeddings, or approve a provider/privacy
model.

## Benefits

- Final release evidence shows the complete memory-quality gate in one artifact.
- Reviewers can see that vector readiness was measured without running a
  separate command.
- A vector experiment cannot silently become release-ready once recall fixtures
  prove FTS misses; it requires explicit review.
- MCP consumers of `memory.release_evidence` receive the same handoff signal as
  the CLI.

## Limitations

- The release-evidence command does not write `reports/vector-readiness.md`;
  use `ai-dememory vector status --write-report` for a standalone generated
  report.
- `vector_readiness_review` is only emitted for the eligible experiment
  decision, not for ordinary fixture freshness problems already covered by
  recall review blockers.
- The feature does not add vector search, embeddings, remote providers, or
  privacy controls.

## Future Work

- Add standalone vector experiment planning only after real recall fixtures make
  the measured case.
- Include provider/privacy diagnostics if a future vector implementation is
  approved.
- Revisit thresholds after the fixture set contains more reviewed misses.

## Dependencies

- ADR 0009 defines the measured vector-search gate.
- ADR 0036 exposes vector readiness over MCP.
- ADR 0110 and ADR 0111 define recall release evidence and review planning.
- ADR 0183 adds setup-health vector readiness.
- `scripts/vector_gate.py` owns vector readiness evaluation.
- `scripts/release_evidence.py` owns release evidence assembly.
