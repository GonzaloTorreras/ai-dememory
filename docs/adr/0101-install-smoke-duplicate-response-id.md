# ADR 0101: Install Smoke Duplicate Response Id Diagnostics

## Status

Accepted.

## Context

ADR 0097 made direct install-smoke MCP validation collect responses by JSON-RPC
request id. The collector still overwrote earlier results if stdout contained
the same response id more than once.

The direct install-smoke payload sends each request id exactly once. A duplicate
response id from the installed package or Docker image is therefore ambiguous
release evidence and should not be silently accepted.

## Decision

Reject duplicate integer response ids in direct install-smoke MCP validation.

The collector now raises an `InstallSmokeError` when a response id has already
been recorded. Response-less notifications remain allowed.

## Benefits

- Prevents later duplicate responses from overwriting earlier package/Docker
  smoke evidence.
- Makes direct MCP smoke logs easier to trust during release review.
- Keeps the response-id contract exact for the fixed install-smoke payload.

## Limitations

- The duplicate check is scoped to direct install-smoke completed output.
- It does not attempt to recover by choosing the first or last response.
- It does not validate duplicate response-less notifications because
  notifications do not have request ids.

## Future Risks

- If direct install smoke starts issuing repeated ids intentionally, the payload
  contract and this validator must change together.
- ADR 0102 later rejects id-bearing responses that omit both `result` and
  `error`.
- If a shared JSON-RPC response collector is introduced, this diagnostic should
  move there to avoid divergent MCP smoke behavior.
- If install smoke adds more request ids, duplicate detection should still apply
  across the expanded expected-id set.

## Dependencies

- ADR 0011 defines the reusable install smoke runner.
- ADR 0097 defines response-id matching for direct install smoke.
- ADR 0098 defines missing-response diagnostics for direct install smoke.
- ADR 0099 defines unexpected integer response-id diagnostics for direct
  install smoke.
- ADR 0100 defines invalid response-id diagnostics for direct install smoke.
- ADR 0102 defines missing result-field diagnostics for direct install smoke.
- `scripts/install_smoke.py` remains the direct installed and Docker MCP stdio
  smoke implementation.
