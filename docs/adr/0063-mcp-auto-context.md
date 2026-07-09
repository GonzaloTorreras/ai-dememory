# ADR 0063: MCP Auto Context

Status: Accepted for the v2 draft.

## Context

Phase 1 of the v2 plan requires token-budgeted context generation, including
`ai-dememory context --auto` for session-start use. The CLI already derived an
auto query from generated working memory, but MCP clients still had to provide
an explicit `query` for `memory.context`.

That mismatch forced clients to read `memory.working_current` or
`memory.working_status`, synthesize their own query text, and then call
`memory.context`. It also made plugin instructions less precise because Codex
could not ask the server for the same auto context that the CLI supports.

## Decision

Add optional auto-query support to MCP `memory.context`:

- explicit query calls continue to pass `query`;
- session-start calls may pass `auto: true` without `query`;
- auto mode derives the query from generated `working/current.json` and
  `working/recent-session.md`;
- the response includes `query_source` with `explicit` or `working_memory`.

The CLI and MCP server share `resolve_context_query` so empty-query handling and
working-memory query derivation stay aligned. Auto queries are secret scanned
before use. The context bundle remains token-budgeted and continues to exclude
restricted memory unless `include_sensitive` is explicitly set.

## Benefits

- Brings MCP parity with the existing CLI `context --auto` workflow.
- Gives Codex and Claude clients a simple session-start context path.
- Makes provenance visible through `query_source` so callers can display or log
  whether context came from an explicit query or generated working state.
- Reduces client-side query synthesis and keeps behavior inside the audited
  local tool.

## Limitations

- Auto context depends on generated working files being present and useful.
- Generated working state is operational context, not reviewed durable memory.
- Auto mode still uses SQLite FTS; it does not add semantic retrieval.
- If working memory is empty, callers must provide an explicit query.

## Future Risks

- Large working snapshots may need summarization before becoming an effective
  query source.
- If generated working state gains schemas or retention policies, auto query
  derivation may need version-aware parsing.
- Clients may over-trust generated working memory unless plugin guidance keeps
  the review boundary clear.

## Dependencies

- ADR 0038 defines MCP working-memory tools and generated-state boundaries.
- ADR 0059 defines context/search explanation metadata.
- `scripts/context_memory.py` remains the shared implementation for CLI and MCP
  context query resolution.
