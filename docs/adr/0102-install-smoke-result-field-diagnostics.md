# ADR 0102: Install Smoke Result Field Diagnostics

## Status

Accepted.

## Context

Direct install-smoke MCP validation already rejects JSON-RPC error responses and
then records each successful response by id. Before this ADR, a response object
with an expected id but without either `result` or `error` was recorded as
`None`.

That malformed response would later fail as a generic protocol or ping-result
problem. Package and Docker smoke logs need to distinguish malformed JSON-RPC
response shape from a valid response with an incorrect result.

## Decision

Require successful direct install-smoke MCP responses to include a `result`
field.

If a response has an id and no `error`, but also lacks `result`, the validator
now raises an id-specific `InstallSmokeError`. Response-less notifications
remain allowed because they do not have request ids.

## Benefits

- Produces clearer package and Docker smoke diagnostics for malformed responses.
- Avoids treating missing `result` as an ordinary `None` result.
- Keeps direct smoke validation aligned with the expected `initialize` and
  `ping` response shapes.

## Limitations

- The check is scoped to direct install-smoke responses, not all MCP sessions.
- It does not validate the full JSON-RPC envelope beyond the fields needed by
  the direct smoke.
- It still lets the later protocol and ping assertions validate result content.

## Future Risks

- If direct install smoke adds requests where `null` is an expected result,
  presence of `result` should remain distinct from result value.
- ADR 0103 later validates the object type for direct `initialize` and `ping`
  results.
- If a shared JSON-RPC validator is introduced, this shape check should move
  there.
- If future MCP responses add alternative success fields, this validator must be
  updated with that protocol change.

## Dependencies

- ADR 0011 defines the reusable install smoke runner.
- ADR 0097 defines response-id matching for direct install smoke.
- ADR 0098 defines missing-response diagnostics for direct install smoke.
- ADR 0099 defines unexpected integer response-id diagnostics for direct
  install smoke.
- ADR 0100 defines invalid response-id diagnostics for direct install smoke.
- ADR 0101 defines duplicate response-id diagnostics for direct install smoke.
- ADR 0103 defines result-type diagnostics for direct install smoke.
- `scripts/install_smoke.py` remains the direct installed and Docker MCP stdio
  smoke implementation.
