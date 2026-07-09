# ADR 0237: MCP Publish Plan

## Status

Accepted

## Context

ADR 0236 added `ai-dememory publish-plan` so maintainers can inspect manual
TestPyPI and PyPI workflow dispatch inputs before publishing. The Codex plugin
and local MCP server are the primary review surfaces during release handoffs,
but they could inspect release evidence and roadmap status only indirectly. A
plugin session still had to shell out to the CLI to see the publish workflow
plan.

Publishing must remain explicit and manual. Exposing the plan over MCP must not
turn MCP into a package release channel or let a client trigger uploads.

## Decision

Expose read-only MCP tool `memory.publish_plan`.

The tool accepts:

- `repository`, either `testpypi` or `pypi`, defaulting to `testpypi`;
- optional `pr_url` for release evidence context; and
- optional `command` for rendered preflight command arrays.

It returns the same structured payload as `ai-dememory publish-plan --json`,
including workflow path, dispatch inputs, guard issues, release blockers,
manual acceptance and recall fixture status, preflight commands, next actions,
and side-effect flags.

The tool is annotated read-only and returns `publishes_package=false`,
`runs_publish_commands=false`, `runs_preflight_commands=false`, and
`writes_files=false`. It also returns `runs_commands=true` because the planner
may run local read-only inspection commands, such as git status and remote URL
checks, while building the plan. It does not dispatch GitHub Actions, upload
packages, contact PyPI, record acceptance evidence, or write reports. Plain
vault roots return unavailable release evidence inside the plan instead of
failing the MCP call.

## Consequences

- Codex plugin sessions can inspect publish readiness without shelling out.
- MCP runtime smoke now proves the plan can be called over stdio and remains
  non-publishing.
- The plugin enabled-tool allowlist includes `memory.publish_plan`, and release
  guards keep the checked-in plugin config and docs aligned.

## Limitations

- The tool still cannot verify external PyPI/TestPyPI Trusted Publisher
  settings or GitHub environment protection rules.
- It does not prove a real TestPyPI publish happened.
- It does not replace manual acceptance evidence or explicit human approval to
  publish.

## Future Work

- Add optional post-TestPyPI verification planning after real TestPyPI evidence
  defines the expected checks.
- Revisit MCP Registry publication only after PyPI/TestPyPI and real-client
  local MCP acceptance are complete.
- Add connector-backed workflow URL resolution only if release dashboards need
  live GitHub metadata.

## Dependencies

- ADR 0012 defines the manual Trusted Publishing guard.
- ADR 0076 defines publish workflow preflight gates.
- ADR 0127 defines package and Docker smoke gates in publish preflight.
- ADR 0128 defines TestPyPI manual acceptance evidence requirements.
- ADR 0194 defines MCP release evidence report rendering.
- ADR 0233 defines MCP roadmap status.
- ADR 0236 defines the CLI publish plan.
- `scripts/publish_plan.py` owns the publish plan payload.
- `mcp/server/memory_mcp.py` owns MCP tool exposure.
- `plugins/ai-dememory/.mcp.json` owns the plugin allowlist.

## References

- `mcp/server/memory_mcp.py`
- `scripts/publish_plan.py`
- `scripts/mcp_runtime_smoke.py`
- `docs/codex-plugin.md`
- `mcp/README.md`
- `tests/test_memory_tools.py`
