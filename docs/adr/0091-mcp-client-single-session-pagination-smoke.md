# ADR 0091: MCP Client Single-Session Pagination Smoke

## Status

Accepted.

## Context

ADR 0088 made `mcp-client-smoke` follow `tools/list` pagination when verifying
plugin or client config `enabled_tools`. It relaunched the configured local MCP
server for each page. That matched the current cursor implementation, but it
left a compatibility gap if future cursors become connection-bound.

The v2 install UX depends on checked-in plugin and generated client config
smoke tests proving the same stdio behavior a real local client will use.

## Decision

Update `scripts/mcp_client_smoke.py` so `enabled_tools` verification launches
the configured MCP command once, performs `initialize` and `ping`, and follows
all `tools/list` cursors in that same stdio session.

The existing lightweight batch `initialize`/`ping` smoke remains for configs
without `enabled_tools`. Paginated allowlist verification now uses an
interactive JSON-RPC helper with bounded response waits and process cleanup.

ADR 0092 later adds `notifications/initialized` to both client-smoke paths so
this single-session flow follows the standard lifecycle ordering before ping and
tool listing.

## Benefits

- Removes the stateless-cursor assumption from plugin allowlist verification.
- Matches real MCP client behavior more closely while preserving generated and
  checked-in config coverage.
- Keeps the smoke sensitive to future cursor implementations that are valid
  only within one server session.

## Limitations

- The smoke still verifies tool advertisement, not execution of every enabled
  tool.
- The response timeout is intentionally simple and local; it is not a full MCP
  client implementation.
- Configs without `enabled_tools` still run the lighter initialize/ping path.

## Future Risks

- If MCP clients add more required lifecycle notifications, this helper should
  add them after negotiation.
- If server output includes non-JSON diagnostic lines on stdout, the parser may
  need to skip or classify those lines.
- If the MCP spec adds batch or streaming list semantics, this smoke should
  adopt the official behavior instead of local request loops.

## Dependencies

- ADR 0069 defines checked-in plugin MCP config smoke coverage.
- ADR 0087 defines config-file `enabled_tools` verification.
- ADR 0088 defines paginated `tools/list` allowlist verification.
- ADR 0092 defines initialized-notification coverage for this smoke.
- `scripts/mcp_client_smoke.py` remains the shared MCP client launch smoke.
