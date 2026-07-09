# ADR 0021: Expanded MCP Runtime Smoke

## Status

Accepted for v2 draft.

## Context

The v2 release checklist requires the PR-gated MCP runtime smoke to verify more
than protocol startup. It should prove that newer local-memory surfaces for
recall misses, lifecycle scoring, provider imports, scheduler planning, manual
acceptance readiness, hooks, sleep consolidation, maintenance status, and review
workflows are callable over MCP and keep writes inside review or
generated-artifact directories.

Before this ADR, `ai-dememory mcp-smoke` verified lifecycle negotiation, ping,
inventory listing, search/context/graph, sensitive resource filtering,
`memory.write_proposal`, `memory.capture_import`, and a path-boundary rejection.
It listed all tools but did not execute many newer v2 tools.

## Decision

Expand `scripts/mcp_runtime_smoke.py` so its temporary fixture vault exercises:

- `memory.reindex`, `memory.mark_seen`, `memory.outcome`, and
  `memory.lifecycle_scores`
- `memory.capture_miss`
- `memory.import_chats`, `memory.capture_import`, and `memory.providers_detect`
- `memory.maintenance_status`
- `memory.schedule_plan`
- `memory.acceptance_status` and `memory.acceptance_verify`
- `memory.hook_events` and `memory.hook_config`
- `memory.sleep_plan` and `memory.sleep_apply_reviewed`
- `memory.review_false_positives`, `memory.false_positive_ignore`,
  `memory.review_conflicts`, `memory.conflict_merge_proposal`,
  `memory.review_modes`, and `memory.review_plan`

The smoke still requires `AI_DEMEMORY_PR_URL` unless explicitly bypassed for
local debugging. Write-capable tools run only against a temporary fixture vault.
ADR 0089 later strengthens list-method coverage by following pagination cursors
for tools, resources, and prompts.
ADR 0107 later runs this PR-gated smoke in CI for pull request events by setting
`AI_DEMEMORY_PR_URL` from the GitHub pull request URL.

## Benefits

- Makes the MCP runtime smoke match the v2 checklist more closely.
- Keeps inventory listing coverage aligned with paginated MCP list methods.
- Proves write-capable tools stay under `inbox/`, `.ai-dememory-ignore.toml`,
  or generated index/report locations in a disposable vault.
- Catches integration regressions that static inventory checks cannot detect.
- Keeps real user memory untouched during PR validation.
- Makes the same runtime fixture set suitable for CI PR validation.

## Limitations

- The smoke validates representative payloads, not exhaustive tool schemas.
- It does not use a real GUI MCP client; that remains manual acceptance.
- It does not install OS schedules or hooks. It verifies generated commands and
  config fragments only.
- It intentionally uses fake fixture data and redacted fake secrets.

## Future Risks

- Additional MCP tools need matching fixture assertions or the smoke will drift.
- Runtime smoke duration can grow as more write-capable tools are added.
- If tool outputs change shape, this smoke will need to be updated with the
  server change.
- If CI runtime duration grows too much, the PR-gated smoke may need fixture
  partitioning instead of weakening the PR URL gate.

## Dependencies

- ADR 0107 defines the CI pull-request workflow integration.
- `scripts/mcp_runtime_smoke.py` remains the executable runtime smoke.
