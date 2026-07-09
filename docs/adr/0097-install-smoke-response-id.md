# ADR 0097: Install Smoke Response Id Matching

## Status

Accepted.

## Context

ADR 0096 made the direct install-smoke MCP payload send
`notifications/initialized` before `ping`. The validator still assumed stdout
position: the first JSON object was the initialize response and the second was
the ping response.

Valid MCP servers may emit response-less notifications on stdout. A valid
notification before or between responses would shift fixed-position parsing and
make the installed package or Docker image smoke fail for the wrong reason.

## Decision

Update `scripts/install_smoke.py` so direct MCP smoke validation parses stdout
messages, skips response-less notifications, fails explicit JSON-RPC errors, and
matches responses by integer request id.

The validator now checks response id `1` for protocol `2025-11-25` and response
id `2` for the empty `ping` result.

## Benefits

- Aligns install-smoke response handling with MCP client and runtime smoke.
- Avoids false failures when a valid server emits notifications during startup.
- Gives clearer errors when the server returns a JSON-RPC error for a direct
  install-smoke request.

## Limitations

- The direct install-smoke validator still handles a fixed two-request payload.
- It skips non-integer ids because the direct smoke only sends integer ids.
- It validates completed process output, not a live asynchronous response
  stream.

## Future Risks

- If the direct install smoke grows beyond `initialize` and `ping`, expected
  request ids should be represented as a table instead of hard-coded ids.
- ADR 0098 later adds explicit diagnostics for missing initialize and ping
  response ids.
- If servers emit many unrelated integer-id responses, the validator may need a
  duplicate or unexpected-id diagnostic.
- If install smoke needs long-lived sessions, response matching should move into
  the same streaming helper used by client/runtime smoke.

## Dependencies

- ADR 0011 defines the reusable install smoke runner.
- ADR 0094 defines response-id matching for MCP client config smoke.
- ADR 0095 defines response-id matching for PR-gated runtime smoke.
- ADR 0096 defines initialized-notification coverage for direct install smoke.
- ADR 0098 defines missing-response diagnostics for direct install smoke.
- `scripts/install_smoke.py` remains the direct installed and Docker MCP stdio
  smoke implementation.
