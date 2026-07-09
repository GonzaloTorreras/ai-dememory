# ADR 0131: MCP Recall Miss Candidate Check

## Status

Accepted.

## Context

ADR 0130 added the CLI command `ai-dememory recall-fixtures check-miss` so
reviewers can verify whether a query and expected memory form a real recall
miss candidate before writing feedback. MCP clients already expose recall
capture, fixture freshness, review planning, and reviewed miss outcomes, but
they could not run the read-only candidate check.

That left plugin and MCP users with a weaker workflow than CLI users: they
could write `memory.capture_miss`, but not inspect the rank evidence first
through the same local client.

## Decision

Expose `memory.recall_miss_candidate` as a read-only MCP tool.

The tool accepts `query` plus exactly one expected target through
`expected_id` or `expected_path`, then delegates to the same candidate checker
as the CLI. It returns the expected rank, whether the query is a candidate miss,
top search results, capture commands only when the miss is a candidate, and
`writes_files: false`.

The Codex plugin allowlist includes this tool because it is review-first and
does not write files, fixtures, reports, indexes, or canonical memory.

## Benefits

- Gives MCP clients the same pre-capture recall review workflow as the CLI.
- Reduces accidental `memory.capture_miss` writes from queries that already
  rank correctly.
- Keeps plugin recall-quality work local, auditable, and review-first.
- Lets PR-gated MCP smoke verify the read-only candidate contract.

## Limitations

- The tool requires an existing generated search index.
- It does not satisfy recall fixture freshness or manual release acceptance.
- It cannot promote, reject, dismiss, or write recall miss files.

## Future Risks

- If the CLI candidate schema changes, the MCP output schema and runtime smoke
  assertions must stay in sync.
- If vector search is added later, the response should identify the retrieval
  backend used to compute the rank.
- If clients log full result snippets, sensitive-but-not-secret query context
  may need additional client-side handling.

## Dependencies

- ADR 0130 defines the CLI recall miss candidate checker.
- ADR 0046 defines MCP recall review planning.
- ADR 0113 defines MCP recall miss review outcomes.
- `scripts/recall_fixtures.py` owns candidate-check semantics.
- `mcp/server/memory_mcp.py` owns the MCP tool schema and dispatch.
