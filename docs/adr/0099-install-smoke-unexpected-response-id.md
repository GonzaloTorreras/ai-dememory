# ADR 0099: Install Smoke Unexpected Response Id Diagnostics

## Status

Accepted.

## Context

ADR 0097 made direct install-smoke MCP validation match stdout responses by
JSON-RPC request id, and ADR 0098 added explicit diagnostics for missing
expected ids. The direct smoke sends only two requests: initialize id `1` and
ping id `2`.

If the installed package or Docker image returns an additional integer response
id, that output cannot correspond to a request sent by the direct smoke. Ignoring
it would hide protocol contamination in package and image release logs.

## Decision

Treat integer response ids other than `1` and `2` as direct install-smoke
failures.

Response-less notifications remain allowed. ADR 0100 later rejects non-integer
response ids because this direct smoke only sends integer ids and the broader
client/runtime smokes own full session behavior.

## Benefits

- Surfaces protocol contamination in installed and Docker direct MCP smokes.
- Keeps direct smoke diagnostics aligned with the fixed request payload.
- Prevents unexpected responses from being silently accepted in release logs.

## Limitations

- The allowed id set is hard-coded to the current direct smoke payload.
- ADR 0100 later makes non-integer response ids explicit failures.
- This remains a completed-output validator, not a streaming MCP dispatcher.

## Future Risks

- If install smoke adds MCP requests, the expected id set must be updated with
  the payload.
- If the direct smoke starts using string ids, ADR 0100's diagnostic contract
  needs to move from integer-only to exact id matching.
- If valid server-side behavior later includes request-like output, this check
  may need to distinguish response ids from other JSON-RPC message shapes.

## Dependencies

- ADR 0011 defines the reusable install smoke runner.
- ADR 0097 defines response-id matching for direct install smoke.
- ADR 0098 defines missing-response diagnostics for direct install smoke.
- ADR 0100 defines invalid response-id diagnostics for direct install smoke.
- `scripts/install_smoke.py` remains the direct installed and Docker MCP stdio
  smoke implementation.
