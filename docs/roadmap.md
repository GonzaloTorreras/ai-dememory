# Roadmap

This is the only active product plan. It is intentionally not a large DAG.

## Completed

- First vertical MVP: setup once, save one human-approved memory from
  any directory, atomically read it back and return an understandable result.
- Saving remains independent from search, modules, MCP, network, models and
  background processes.
- Second vertical MVP: recall a saved memory from any directory with a clear
  match count and an explicit empty result.
- SQLite remains lazy and disposable; ranking stays unchanged until retrieval
  failures are measured.

## Now

- Third vertical MVP: list one AI proposal, inspect it and explicitly accept or
  reject it without allowing modules to write canonical memory directly.
- Make the human decision and resulting state obvious before expanding review
  policy or automation.
- Prove review in isolation before running the broader V3 regression suite.

## Next

- Exercise review and the optional MCP module as separate vertical slices;
  neither may become a dependency of saving or recall.
- Prove modules are lazy and MCP exposes exactly five tools.
- Test the alpha in real Codex, Claude and Hermes sessions using the same MCP
  module, beginning read-only/proposal-only.
- Measure startup time, RSS, index growth and recall usefulness on a real but
  private vault.
- Add import/export only for a demonstrated source and keep it an optional
  module.
- Improve search or ranking only from reviewed misses.

## Later

- A small local dashboard for browsing and reviewing, as an optional module.
- Provider-specific hooks only after the core works without them.
- Deterministic consolidation candidates only after enough real proposals exist
  to measure usefulness.
- Vector or model-assisted retrieval only if FTS has a measured gap.

## Not planned without evidence

Daemon, cloud sync, multi-user service, autonomous canonical writes, automatic
chat ingestion, graph database, default Node runtime, model synthesis, another
admin CLI, or compatibility with the unused V2 design.

## Release gates

- Replace remaining active V2 packaging/documentation references with V3 truth.
- Physically remove the inert V2 tree only as a separately approved cleanup.
- Publish `3.0.0a1` only after fresh review, green CI and explicit release
  authorization.
