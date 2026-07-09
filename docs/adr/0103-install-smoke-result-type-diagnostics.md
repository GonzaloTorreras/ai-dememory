# ADR 0103: Install Smoke Result Type Diagnostics

## Status

Accepted.

## Context

ADR 0102 made direct install-smoke MCP validation require a `result` field on
successful id-bearing responses. The validator still assumed the values were
objects. A non-object initialize result could raise an implementation exception
instead of an `InstallSmokeError`, and a non-object ping result produced a
generic empty-result mismatch.

Package and Docker smoke logs need to distinguish malformed result types from
valid object results with incorrect content.

## Decision

Require the direct install-smoke `initialize` and `ping` results to be JSON
objects before validating their content.

The validator now raises explicit `InstallSmokeError` messages for non-object
initialize and ping results, then continues to check protocol version and empty
ping object for valid object results.

## Benefits

- Prevents implementation exceptions from leaking into release smoke output.
- Produces clearer package and Docker diagnostics for malformed result values.
- Keeps direct install-smoke validation aligned with expected MCP lifecycle
  result shapes.

## Limitations

- This check is specific to the direct install-smoke `initialize` and `ping`
  payload.
- It does not validate all fields of the initialize result.
- It still relies on later assertions for protocol version and exact empty ping
  content.

## Future Risks

- If the direct smoke adds requests with non-object successful results, result
  type expectations should become request-specific.
- ADR 0104 later separates missing, invalid, and mismatched initialize
  `protocolVersion` diagnostics.
- If MCP changes the lifecycle result shapes, this validator must change with
  the protocol version.
- If a shared JSON-RPC/MCP result validator is introduced, this logic should move
  there to avoid drift.

## Dependencies

- ADR 0011 defines the reusable install smoke runner.
- ADR 0097 defines response-id matching for direct install smoke.
- ADR 0102 defines result-field diagnostics for direct install smoke.
- ADR 0104 defines initialize protocol-version diagnostics for direct install
  smoke.
- `scripts/install_smoke.py` remains the direct installed and Docker MCP stdio
  smoke implementation.
