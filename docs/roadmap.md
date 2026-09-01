# Roadmap

This is the only active product plan. It is intentionally not a large DAG.

## Now

- Prove the clean flow: setup, remember, recall, review and status.
- Prove modules are lazy and MCP exposes exactly five tools.
- Replace V2 CI, packaging and public documentation with V3 truth.
- Physically remove the excluded V2 runtime, tests, guards, ADRs and planning
  contracts after the one-time destructive cleanup receives explicit approval.
- Publish `3.0.0a1` only after a fresh independent review and explicit release
  authorization.

## Next

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
