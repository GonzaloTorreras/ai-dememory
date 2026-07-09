# ADR 0098: Install Smoke Missing Response Diagnostics

## Status

Accepted.

## Context

ADR 0097 made direct install-smoke MCP validation match stdout responses by
JSON-RPC request id. After that change, a missing initialize or ping response
would still fall through to the generic protocol or ping result checks.

Those generic failures make package and Docker smoke logs harder to interpret,
especially when the server emits notifications or unrelated responses but never
answers one of the direct smoke requests.

## Decision

Require the direct install-smoke validator to explicitly observe response id `1`
for `initialize` and response id `2` for `ping` before validating their results.

Missing response ids now produce id-specific `InstallSmokeError` messages.

## Benefits

- Makes package and Docker smoke failures easier to triage from CI logs.
- Distinguishes a wrong protocol result from a missing initialize response.
- Distinguishes a non-empty ping result from a missing ping response.

## Limitations

- The direct validator still only knows about the fixed two-request payload used
  by install smoke.
- ADR 0099 later makes unrelated integer response ids an explicit failure.
- It does not add streaming timeouts because `subprocess.run` already bounds the
  direct install-smoke process.

## Future Risks

- If install smoke adds more MCP requests, each expected request id should get a
  named diagnostic.
- ADR 0099 keeps the allowed response-id set coupled to the fixed request
  payload.
- If the smoke starts using non-integer JSON-RPC ids, this diagnostic contract
  must change with the payload.
- If direct smoke starts issuing concurrent requests, diagnostics should move to
  a shared response collector.

## Dependencies

- ADR 0011 defines the reusable install smoke runner.
- ADR 0096 defines initialized-notification coverage for direct install smoke.
- ADR 0097 defines response-id matching for direct install smoke.
- ADR 0099 defines unexpected response-id diagnostics for direct install smoke.
- `scripts/install_smoke.py` remains the direct installed and Docker MCP stdio
  smoke implementation.
