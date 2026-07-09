# ADR 0092: MCP Client Initialized Notification Smoke

## Status

Accepted.

## Context

ADR 0091 moved `mcp-client-smoke` paginated `tools/list` verification into one
stdio session. The helper still performed `initialize` and then immediately ran
`ping` and `tools/list`.

Real MCP clients normally send the lifecycle notification
`notifications/initialized` after negotiation. The server already accepts this
notification, but the generated and checked-in client config smoke did not prove
that local setup paths can run with that standard lifecycle ordering.

## Decision

Update `scripts/mcp_client_smoke.py` to send
`notifications/initialized` after `initialize` and before `ping`.

Both smoke paths now use that ordering:

- generated or config-file smoke without `enabled_tools`
- config-file `enabled_tools` verification with paginated `tools/list`

The notification is sent as a JSON-RPC notification without an `id`; the smoke
does not wait for a response.

ADR 0094 later makes the client smoke match JSON-RPC responses by id and skip
response-less server notifications after initialization.

## Benefits

- Makes client config smoke closer to real MCP client lifecycle behavior.
- Proves plugin allowlist verification still works when a server expects the
  initialized notification before tool listing.
- Keeps the lifecycle requirement in automated install and plugin smoke instead
  of relying only on direct unit coverage of the server handler.

## Limitations

- The smoke still does not implement the full MCP client lifecycle state
  machine.
- It does not verify client behavior after shutdown or cancellation.
- It assumes the initialized notification remains response-less JSON-RPC.

## Future Risks

- If the MCP lifecycle changes notification names or required ordering, the
  smoke helper and docs should be updated together.
- If clients require capability negotiation before sending the notification,
  generated configs may need capability-specific smoke variants.
- If the server starts emitting high-volume post-initialization notifications,
  stdout parsing may need notification limits or richer diagnostics.

## Dependencies

- ADR 0014 defines generated MCP client config smoke.
- ADR 0069 defines checked-in plugin MCP config smoke coverage.
- ADR 0091 defines single-session paginated `tools/list` verification.
- ADR 0094 defines response-id matching and server-notification skipping.
- `scripts/mcp_client_smoke.py` remains the shared MCP client launch smoke.
