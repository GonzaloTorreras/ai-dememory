# ADR 0130: Recall Miss Candidate Check

## Status

Accepted.

## Context

Final v2 release evidence intentionally blocks on a reviewed promotion from a
real retrieval miss. ADR 0129 added `capture-miss --dry-run`, but reviewers
still had to manually compare search results before deciding whether a query
was actually outside the accepted rank window.

That gap made the recall-quality blocker harder to clear without weakening the
review requirement. The tool needed a read-only way to show the expected memory
rank, top search results, and the exact capture command to run if the miss is
real.

## Decision

Add `ai-dememory recall-fixtures check-miss`.

The command accepts a query plus exactly one expected target:

- `--expected-id <memory-id>`
- `--expected-path <path-inside-vault>`

It searches the generated index, resolves expected paths to memory ids, reports
the expected rank, marks `candidate_miss: true` only when the expected memory is
absent from the inspected results or ranked below `--min-rank`, and emits
read-only `capture-miss` next-step commands only for candidate misses. JSON output includes
`writes_files: false` and the top result details. The command never writes
recall feedback, fixtures, reports, indexes, or canonical memory.

## Benefits

- Gives reviewers reproducible evidence before creating a recall miss file.
- Reduces accidental fixture pollution from queries that already rank well.
- Keeps the release blocker tied to real search behavior.
- Lets install smoke verify the recall review helper after package install.

## Limitations

- A candidate is still not release evidence until a reviewer writes, reviews,
  and promotes a miss.
- The command depends on an existing generated search index.
- If the expected memory is absent from the inspected limit, the command cannot
  prove whether it appears at a lower rank; it only proves it missed the
  configured acceptance window.

## Future Risks

- If ranking changes substantially, reviewers may need to adjust default
  `--min-rank` or `--limit` values.
- If recall candidate checks are exposed over MCP later, client logs must avoid
  retaining sensitive queries.
- If vector search experiments are added, candidate checks should continue to
  report which retrieval backend produced the rank.

## Dependencies

- ADR 0017 defines reviewed recall miss promotion.
- ADR 0110 defines recall freshness as a release blocker.
- ADR 0129 defines recall miss dry-run capture.
- `scripts/recall_fixtures.py` owns recall review planning and candidate checks.
- `scripts/search_memory.py` owns local ranked retrieval.
