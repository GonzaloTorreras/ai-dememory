# Future Vector Migration

Do not implement vectors for the MVP. Markdown remains canonical and SQLite FTS
is the first retrieval layer.

## Trigger Criteria

Add vector search only when recall logs show it is justified:

- More than 10-15% of important searches fail with SQLite FTS.
- Relevant memories frequently use different vocabulary from user queries.
- `retrieval_log` and manual review show semantic retrieval would have returned
  useful memories that FTS missed.
- The added dependency and operational cost are worth the recall improvement.
- `ai-dememory eval-recall` shows repeated fixture failures after metadata,
  alias, and ranking tuning have been considered.

Run the explicit gate:

```bash
ai-dememory vector status --json
ai-dememory vector status --write-report
ai-dememory vector status --write-report --report-path reports/vector-readiness.md
```

The default gate requires recall below `0.85` and at least two failing recall
cases before it reports `eligible_for_vector_experiment`. Any weaker result
means FTS tuning, aliases, metadata, or better fixtures should come first.
Custom report paths must stay inside the memory root, and the rendered Markdown
report is secret-scanned before writing.

## Candidate Backends

- `sqlite-vec`: first choice for local, simple, SQLite-adjacent storage.
- LanceDB: useful if local collections grow beyond the SQLite comfort zone.
- turbopuffer: managed option only if cloud scale or shared remote retrieval is
  required.
- Quantized or compressed embeddings: only if embedding size becomes a measured
  bottleneck.

## Data Contract

- Embeddings are generated artifacts keyed by `memory_id`.
- Embeddings and vector indexes must be reproducible from Markdown.
- Vector data must never become canonical memory.
- `secret-prohibited` memories remain excluded.
- Vector search augments FTS; it does not replace metadata filters, source paths,
  confidence, status, or human review.

## Future Hybrid Score

`PLAN.md` R7 covers the broader super-search direction: fuzzy lexical matching,
candidate-bundle review, optional graph/vector signals, and an optional
low-latency retrieval reviewer connector. That work is still gated by policy,
privacy, traceability, and measured fixture failures; it should not be treated
as permission to enable vectors by default.

```text
score =
  0.35 * fts_score +
  0.30 * vector_score +
  0.10 * tag_match +
  0.10 * recency +
  0.10 * confidence +
  0.05 * pin/type_boost
```

Before implementation, collect a small benchmark set in
`quality/recall-fixtures.json` so vector recall can be measured rather than
assumed.
