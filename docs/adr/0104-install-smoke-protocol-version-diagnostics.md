# ADR 0104: Install Smoke Protocol Version Diagnostics

## Status

Accepted.

## Context

ADR 0103 made direct install-smoke MCP validation require object results for
`initialize` and `ping`. The initialize content check still treated missing,
non-string, and wrong `protocolVersion` values as the same generic negotiation
failure.

Package and Docker smoke logs should show whether the server omitted the
protocol field, returned it with the wrong type, or negotiated a different
protocol version.

## Decision

Validate the direct install-smoke initialize `protocolVersion` field in three
steps:

1. Require the field to be present.
2. Require the value to be a string.
3. Require the value to equal `2025-11-25`.

Each failure path now raises a distinct `InstallSmokeError`.

## Benefits

- Makes release smoke failures easier to triage from package and Docker logs.
- Distinguishes malformed initialize responses from valid negotiation of the
  wrong protocol.
- Keeps the direct install-smoke lifecycle contract explicit.

## Limitations

- The accepted protocol is still fixed to the v2 release target.
- The check does not validate other initialize result fields.
- The validator remains scoped to direct install-smoke `initialize`/`ping`
  behavior, not a general MCP negotiation library.

## Future Risks

- If the v2 target protocol changes, the expected value and docs must change
  together.
- If install smoke starts accepting multiple protocol versions, this check
  should use an allowlist with explicit diagnostics.
- If a shared MCP lifecycle validator is introduced, this check should move
  there to avoid drift.

## Dependencies

- ADR 0011 defines the reusable install smoke runner.
- ADR 0096 defines initialized-notification coverage for direct install smoke.
- ADR 0103 defines result-type diagnostics for direct install smoke.
- `scripts/install_smoke.py` remains the direct installed and Docker MCP stdio
  smoke implementation.
