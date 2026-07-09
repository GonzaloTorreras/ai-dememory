# ADR 0095: MCP Runtime Response Id Smoke

## Status

Accepted.

## Context

ADR 0093 made PR-gated `mcp-smoke` send `notifications/initialized` before
`ping`. The runtime smoke still read the next stdout JSON object as the response
to the request it had just sent.

Valid MCP servers may emit response-less notifications after initialization. If
runtime smoke consumes one of those notifications as a response, it can fail a
valid server lifecycle or hide the actual response from a later check.

## Decision

Update `scripts/mcp_runtime_smoke.py` so request handling matches JSON-RPC
responses by `id`.

For every request with an integer `id`, runtime smoke now reads stdout until it
finds a message with the same `id`. Response-less server notifications are
skipped before normal error/result validation.

## Benefits

- Makes PR-gated runtime smoke tolerant of valid server notifications.
- Aligns runtime smoke response handling with client-config smoke from ADR 0094.
- Reduces false negatives in lifecycle and list/tool checks if the server later
  emits local diagnostics as MCP notifications.

## Limitations

- Runtime smoke still runs requests sequentially and is not a full asynchronous
  JSON-RPC dispatcher.
- Responses with unrelated ids are skipped rather than reported immediately as
  protocol failures.
- Non-JSON stdout remains a smoke failure.

## Future Risks

- High-volume notifications may require a bounded notification skip count before
  timing out.
- If runtime smoke starts issuing concurrent requests, response handling should
  move to a shared dispatcher.
- If the server emits structured diagnostics on stderr, this smoke still only
  uses stderr as failure context.

## Dependencies

- ADR 0021 defines broad PR-gated MCP runtime smoke coverage.
- ADR 0093 defines initialized-notification coverage for runtime smoke.
- ADR 0094 defines response-id matching for MCP client config smoke.
- `scripts/mcp_runtime_smoke.py` remains the PR-gated stdio runtime smoke.
