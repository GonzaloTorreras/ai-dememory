# ADR 0233: MCP Roadmap Status

## Status

Accepted

## Context

ADR 0232 added `ai-dememory roadmap status` so continuation work can inspect
the v2 operational roadmap phases as machine-readable evidence. That command
was available only through the CLI, while the plugin and MCP workflows are the
primary local tool surfaces for Codex sessions.

Without an MCP tool, clients can inspect setup health, release evidence, recall
quality, vector readiness, and review queues, but not the roadmap status that
ties those areas together.

## Decision

Expose read-only MCP tool `memory.roadmap_status`.

The tool returns the same structured payload as `ai-dememory roadmap status`:
phase count, status counts, phase evidence paths, missing evidence, read-only
flags, and next actions. It is included in the plugin enabled-tool allowlist,
runtime smoke, MCP inventory documentation, and release/plugin guards.

The tool uses read-only MCP annotations and does not write reports, mutate
canonical memory, record acceptance evidence, run commands, or enable vector
search.

## Consequences

- Codex plugin sessions can inspect the v2 roadmap state without shelling out.
- Runtime smoke proves the tool works over stdio and remains read-only.
- MCP inventory and plugin guards catch drift if the tool is removed from docs
  or the enabled-tool allowlist.
- Plain vault roots may report missing implementation evidence, which is useful
  because roadmap implementation evidence lives in the distribution checkout.

## Limitations

- The tool reports representative evidence paths; it does not run every phase's
  full behavioral test suite.
- In a plain vault, implementation evidence paths may be missing because the
  command is not running from the distribution checkout.
- It does not replace `release-check`, `release-evidence`, manual acceptance,
  recall fixture freshness, or CI.

## Future Work

- Add an `available` wrapper only if clients need distribution-only semantics
  instead of missing-evidence reporting for plain vaults.
- Add per-phase test summaries if tests become tagged by roadmap phase.
- Include PR links for phase evidence if release handoffs need remote
  provenance.

## Dependencies

- ADR 0232 defines CLI roadmap status.
- ADR 0010 defines MCP inventory drift checks.
- ADR 0068 defines plugin MCP enabled-tool drift checks.
- ADR 0107 defines PR-gated MCP runtime smoke.
- `scripts/roadmap_status.py` owns the status payload.

## References

- `mcp/server/memory_mcp.py`
- `scripts/mcp_runtime_smoke.py`
- `plugins/ai-dememory/.mcp.json`
- `docs/codex-plugin.md`
- `tests/test_memory_tools.py`
