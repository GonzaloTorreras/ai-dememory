# ADR 0087: MCP Client Enabled Tools Smoke

## Status

Accepted.

## Context

`ai-dememory mcp-client-smoke` launches generated or checked-in MCP client
configurations and verifies `initialize` plus `ping`. The Codex plugin config
also carries an `enabled_tools` allowlist, and release checks compare that
allowlist against the expected repository list.

That static check can still miss a runtime mismatch. A checked-in config could
name a tool that matches docs and release expectations but is not actually
advertised by the server launched by the config command.

## Decision

When an MCP client config includes `enabled_tools`, `mcp-client-smoke` now sends
`tools/list` requests after `initialize` and `ping`.

The smoke fails if:

- `enabled_tools` is not an array of strings
- the launched server does not return a `tools/list` response
- the response lacks a tools array
- any enabled tool is absent from the launched server's tool names

Generated configs without an `enabled_tools` allowlist keep the existing
`initialize`/`ping` smoke behavior.

## Benefits

- Proves the checked-in Codex plugin allowlist names tools that the launched
  server actually advertises.
- Catches packaging, import, or tool rename drift earlier than manual plugin
  testing.
- Keeps package install smoke aligned with the plugin marketplace artifact.

## Limitations

- The smoke verifies tool advertisement, not full tool execution for every
  enabled tool.
- The server currently advertises all tools; client-side enforcement of
  `enabled_tools` remains the host application's responsibility.
- The smoke does not prove that a Codex client has refreshed or installed the
  plugin from the repository marketplace.

## Future Risks

- If future MCP clients change allowlist field names, the smoke may need
  client-specific adapters.
- ADR 0088 later closes the first-page-only risk by following `tools/list`
  cursors.
- If plugins gain per-tool approval metadata, the smoke should validate the
  metadata shape separately from tool existence.

## Dependencies

- ADR 0014 defines generated MCP client config smoke.
- ADR 0068 defines the guarded plugin MCP tool surface.
- ADR 0069 defines checked-in plugin MCP config smoke coverage.
- ADR 0086 defines the expanded plugin review receipt tool surface.
- `scripts/mcp_client_smoke.py` remains the shared MCP client launch smoke.
- `plugins/ai-dememory/.mcp.json` remains the checked-in plugin config.
