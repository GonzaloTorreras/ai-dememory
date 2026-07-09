# ADR 0009: Measured Vector Search Gate

## Status

Accepted for v2 draft.

## Context

The repository intentionally keeps Markdown canonical and SQLite FTS as the
default retrieval layer. Vector search can improve semantic recall, but it adds
dependencies, generated embedding artifacts, privacy questions, and operational
cost.

The v2 plan says vector search should only be considered after recall fixtures
show measured FTS misses.

## Decision

Add `ai-dememory vector status` as an evidence gate before any vector
implementation:

```bash
ai-dememory vector status --json
ai-dememory vector status --write-report
```

The command evaluates `quality/recall-fixtures.json` with the existing FTS
search path and emits one of:

- `not_justified`: all fixtures pass
- `investigate_fts_first`: some failures exist, but not enough to justify a
  vector experiment
- `eligible_for_vector_experiment`: recall is below the configured threshold
  and enough cases fail

Default thresholds are:

- recall threshold: `0.85`
- minimum failed cases: `2`

The command can write `reports/vector-readiness.md` by default. `--report-path`
can select another generated report path inside the memory root. The rendered
report is secret-scanned before writing. It does not generate embeddings or
enable vector search.

## Benefits

- Keeps vector search tied to measured recall failures.
- Gives release checks and reviewers a concrete command to run.
- Avoids embedding dependencies and privacy exposure in the v2 local baseline.
- Produces a durable report that can be reviewed before approving a future
  vector experiment.
- Allows local handoff workflows to choose an in-root generated report path.

## Limitations

- The gate is only as strong as the curated recall fixtures.
- It does not estimate whether vectors would fix a failed query.
- It does not compare candidate vector backends or embedding models.
- Custom report paths are still generated artifacts and must not be staged as
  canonical memory.

## Future Risks

- Teams may tune thresholds too low and add vectors prematurely.
- Recall fixtures may overrepresent niche failures.
- If report content starts including more user-provided fields, rendered secret
  scanning must continue to cover the final Markdown output.
- A future vector implementation must separately address secret filtering,
  embedding provider privacy, artifact rebuilds, and hybrid ranking.
