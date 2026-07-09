# ADR 0093: MCP Runtime Initialized Notification Smoke

## Status

Accepted.

## Context

ADR 0092 made `mcp-client-smoke` send `notifications/initialized` after
`initialize` and before `ping` or `tools/list`. The PR-gated runtime smoke still
validated the server by negotiating `initialize` and then immediately calling
`ping`.

The runtime smoke is the broader release gate for stdio server behavior. It
should exercise the same standard MCP lifecycle ordering before it validates
tools, resources, prompts, sensitive-resource filters, and review workflows.

## Decision

Update `scripts/mcp_runtime_smoke.py` so `ai-dememory mcp-smoke` sends
`notifications/initialized` immediately after successful protocol negotiation.

The notification is sent as JSON-RPC without an `id`, and the smoke does not
wait for a response. Runtime smoke output records a
`notifications/initialized` check between `initialize` and `ping`.

ADR 0095 later makes runtime smoke match JSON-RPC responses by id and skip
response-less server notifications after initialization.

## Benefits

- Aligns PR-gated runtime smoke with real MCP client lifecycle behavior.
- Keeps runtime and client-config smoke lifecycle coverage consistent.
- Catches regressions where the stdio server rejects the initialized
  notification before deeper runtime checks run.

## Limitations

- The smoke still does not model a complete MCP client state machine.
- It does not validate shutdown, cancellation, progress, or server-to-client
  notification handling.
- The fixture smoke path remains focused on tool behavior; the PR-gated runtime
  smoke owns lifecycle ordering.

## Future Risks

- If MCP lifecycle ordering changes, the runtime and client-config smoke helpers
  should be updated together.
- If the server emits high-volume notifications after initialization, runtime
  smoke may need notification limits or richer diagnostics.
- If future runtime checks require client capabilities, the initialize payload
  may need explicit capability negotiation.

## Dependencies

- ADR 0021 defines broad PR-gated MCP runtime smoke coverage.
- ADR 0092 defines initialized-notification coverage for MCP client config
  smoke.
- ADR 0095 defines response-id matching and server-notification skipping for
  runtime smoke.
- `mcp/server/memory_mcp.py` remains the stdio MCP server implementation.
- `scripts/mcp_runtime_smoke.py` remains the PR-gated stdio runtime smoke.
