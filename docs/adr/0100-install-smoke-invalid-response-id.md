# ADR 0100: Install Smoke Invalid Response Id Diagnostics

## Status

Accepted.

## Context

ADR 0099 made direct install-smoke MCP validation reject unexpected integer
response ids. The validator still ignored non-integer response ids, including
string ids, even though the direct install-smoke payload only sends integer ids
`1` and `2`.

Ignoring non-integer response ids can hide malformed or contaminated stdout from
the installed package or Docker image during release smoke checks.

## Decision

Treat response ids with non-integer types as direct install-smoke failures.

Response-less notifications remain allowed. Boolean ids are also rejected
because Python treats `bool` as a subclass of `int`, while JSON-RPC ids for this
direct smoke are explicitly the integer ids `1` and `2`.

## Benefits

- Makes the direct install-smoke response contract exact for package and Docker
  release checks.
- Surfaces malformed response ids with a clear diagnostic.
- Keeps response-id validation aligned with the fixed direct smoke payload.

## Limitations

- String JSON-RPC ids may be valid in a general MCP session, but this direct
  smoke does not send them.
- The check belongs to the direct package/Docker smoke path, not to a reusable
  full MCP protocol validator.
- Response-less notifications are still accepted without inspecting their
  payload shape.

## Future Risks

- If direct install smoke starts using string ids, this diagnostic must move to
  exact expected-id matching instead of integer-only validation.
- If additional direct MCP requests are added, their ids should be declared in a
  shared expected-id set.
- ADR 0101 later rejects duplicate response ids so repeated ids cannot overwrite
  earlier direct smoke evidence.
- If the project introduces a general JSON-RPC validator, this local check
  should delegate to it to avoid drift.

## Dependencies

- ADR 0011 defines the reusable install smoke runner.
- ADR 0097 defines response-id matching for direct install smoke.
- ADR 0098 defines missing-response diagnostics for direct install smoke.
- ADR 0099 defines unexpected integer response-id diagnostics for direct
  install smoke.
- ADR 0101 defines duplicate response-id diagnostics for direct install smoke.
- `scripts/install_smoke.py` remains the direct installed and Docker MCP stdio
  smoke implementation.
