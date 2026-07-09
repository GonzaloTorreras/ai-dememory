# ADR 0088: MCP Client Tools List Pagination Smoke

## Status

Accepted.

## Context

ADR 0087 made `mcp-client-smoke` verify config-file `enabled_tools` against the
server's `tools/list` response. The MCP server already supports pagination for
tool, resource, and prompt list methods, although the current 74 MCP tools
inventory fits in one default page.

If the plugin allowlist or server inventory grows beyond one page, a first-page
only smoke could falsely report missing enabled tools or, worse, fail to notice
that verification stopped early.

## Decision

`mcp-client-smoke` now follows `tools/list` cursors when verifying
`enabled_tools`.

For each page it launches the configured server, performs `initialize` and
`ping`, requests `tools/list` with the current cursor, and repeats until the
response has no `nextCursor`. The smoke fails when pagination does not reach the
final page, returns an invalid cursor, or exceeds a safety limit.

ADR 0091 later keeps the same paginated allowlist requirement but replaces the
per-page relaunch strategy with one stdio session so connection-bound cursors are
also covered.

Generated configs without `enabled_tools` still run the lighter
`initialize`/`ping` smoke.

## Benefits

- Keeps plugin allowlist verification correct if the MCP tool inventory grows.
- Preserves timeout behavior by using bounded subprocess launches instead of a
  long-lived interactive smoke loop.
- Makes pagination failure explicit instead of silently validating only the
  first page.

## Limitations

- The smoke assumes list cursors are stable across stateless local server
  launches. That matches the current server implementation.
- The smoke still verifies advertisement only, not execution of every enabled
  tool.
- The safety limit is fixed and may need adjustment if a future server uses very
  small pages.

## Future Risks

- If cursors become connection-bound, this smoke should switch to an interactive
  JSON-RPC session with per-request timeouts.
- If clients add per-tool approval metadata, pagination should verify both tool
  names and metadata across all pages.
- If the MCP spec adds batch listing semantics, the smoke may need to prefer the
  official client behavior.

## Dependencies

- ADR 0069 defines checked-in plugin MCP config smoke coverage.
- ADR 0087 defines config-file `enabled_tools` verification.
- `mcp/server/memory_mcp.py` remains the source of `tools/list` cursor behavior.
- `scripts/mcp_client_smoke.py` remains the shared MCP client launch smoke.
