# ADR 0096: Install Smoke Initialized Notification

## Status

Accepted.

## Context

ADR 0092 and ADR 0093 made the generated MCP client smoke and PR-gated runtime
smoke send `notifications/initialized` after protocol negotiation and before
`ping`. The reusable install smoke still used a direct stdio payload with only
`initialize` and `ping` for both the installed CLI and local Docker image.

That direct probe proved a minimal server path, but it did not prove the
installed package and Docker image accept the standard initialized notification
that real MCP clients send before other requests.

## Decision

Update `scripts/install_smoke.py` so its direct MCP stdio payload sends:

1. `initialize` with protocol `2025-11-25`
2. response-less `notifications/initialized`
3. `ping`

The validator continues to expect two JSON-RPC responses because
`notifications/initialized` is a notification and must not produce a response.

## Benefits

- Aligns installed and Docker direct MCP smoke with real client lifecycle
  ordering.
- Catches packaging or image regressions where the server rejects initialized
  notifications even though generated client smoke would exercise them later.
- Keeps the reusable install smoke consistent with the PR-gated runtime smoke
  and generated client config smoke.

## Limitations

- The direct install-smoke payload remains sequential and only verifies
  `initialize`, `notifications/initialized`, and `ping`.
- ADR 0097 later makes the direct validator skip server notifications and match
  responses by JSON-RPC id.
- It does not replace manual MCP client acceptance evidence.

## Future Risks

- If the MCP lifecycle changes again, this payload and the generated client
  smoke should be updated together.
- If install smoke starts issuing more requests after `ping`, response-id
  matching should use an expected-response table rather than hard-coded ids.
- If Docker entrypoint behavior changes, the same initialized-notification
  payload should remain part of both installed and Docker smoke paths.

## Dependencies

- ADR 0011 defines the reusable install smoke runner.
- ADR 0044 defines Docker generated client config smoke.
- ADR 0092 defines initialized-notification coverage for MCP client config
  smoke.
- ADR 0093 defines initialized-notification coverage for PR-gated runtime smoke.
- ADR 0097 defines response-id matching for direct install smoke.
- `scripts/install_smoke.py` remains the direct installed and Docker MCP stdio
  smoke implementation.
