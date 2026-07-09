# ADR 0094: MCP Client Response Id Smoke

## Status

Accepted.

## Context

ADR 0092 made `mcp-client-smoke` send `notifications/initialized` before ping
and tool listing. The smoke still assumed the next stdout JSON object after a
request was the response to that request.

MCP servers may emit response-less notifications on stdout after initialization.
If the smoke treats a server notification as a response, it can fail a valid
client lifecycle or mask the actual request response.

## Decision

Update `scripts/mcp_client_smoke.py` to classify JSON-RPC messages by `id`.

For interactive paginated `tools/list` verification, the smoke now reads until
it finds a response whose `id` matches the request id. Response-less server
notifications are skipped. For the lightweight generated/config smoke path, the
stdout parser now builds results by response id and ignores response-less
notifications before validating `initialize` and `ping`.

## Benefits

- Makes `mcp-client-smoke` tolerant of valid server notifications.
- Keeps generated and checked-in client config smoke closer to real MCP client
  behavior.
- Protects paginated `enabled_tools` verification from accidentally consuming a
  notification as a tool-list response.

## Limitations

- The smoke still does not implement a full asynchronous JSON-RPC dispatcher.
- Unexpected responses with unrelated ids are skipped rather than reported as a
  protocol failure.
- Non-JSON diagnostics on stdout are still treated as smoke failures.

## Future Risks

- If the server emits high-volume notifications, the simple read loop may need a
  notification limit before timing out.
- If future smoke requests are concurrent, response matching should use a shared
  dispatcher instead of one blocking read loop per request.
- If stderr carries structured diagnostics, this smoke still treats stderr only
  as failure context.

## Dependencies

- ADR 0091 defines single-session paginated `tools/list` verification.
- ADR 0092 defines initialized-notification coverage for MCP client config
  smoke.
- `scripts/mcp_client_smoke.py` remains the shared MCP client launch smoke.
