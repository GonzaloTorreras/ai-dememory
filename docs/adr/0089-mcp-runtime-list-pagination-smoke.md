# ADR 0089: MCP Runtime List Pagination Smoke

## Status

Accepted.

## Context

The MCP server supports pagination for `tools/list`, `resources/list`, and
`prompts/list`. The PR-gated runtime smoke previously called each list method
once and validated only the first page. That was enough for the current default
page size, but it left a drift risk if tool, resource, or prompt counts grow or
if the server page size changes.

ADR 0088 closed the same first-page risk for `mcp-client-smoke` enabled-tool
verification. The runtime smoke should provide the same protection for the
server inventory and sensitive-resource filters it validates.

## Decision

Update `scripts/mcp_runtime_smoke.py` to follow `nextCursor` for MCP list
methods.

The smoke now collects all pages for:

- `tools/list`
- `resources/list`
- `prompts/list`

It fails when a page lacks the expected array, returns an invalid cursor, never
reaches the final page, or exceeds a bounded page limit.

## Benefits

- Keeps PR-gated runtime smoke valid if list responses become multi-page.
- Prevents sensitive resource filtering checks from inspecting only the first
  resources page.
- Aligns runtime smoke behavior with the stronger config-file smoke in ADR
  0088.

## Limitations

- The smoke verifies list pagination and selected follow-up behavior, not every
  tool execution across every page.
- It assumes cursors are stable within one stdio server session.
- The page safety limit is fixed and may need adjustment if page sizes become
  very small.

## Future Risks

- If MCP pagination semantics change, the smoke helper should be updated before
  widening the server inventory.
- If resources become very numerous, runtime smoke may need fixture-specific
  filters to avoid slow full-list checks.
- If clients depend on partial page rendering, separate client-level tests may
  be needed.

## Dependencies

- ADR 0021 defines broad PR-gated MCP runtime smoke coverage.
- ADR 0088 defines paginated `tools/list` verification for MCP client config
  smoke.
- `mcp/server/memory_mcp.py` remains the source of list cursor behavior.
- `scripts/mcp_runtime_smoke.py` remains the PR-gated stdio runtime smoke.
