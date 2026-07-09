# ADR 0143: Hook JSON Fingerprints

## Status

Accepted

## Context

ADR 0141 made hook capture idempotent by reusing existing inbox candidates with
the same provider, event, and payload fingerprint. Hook clients usually send
JSON context, but equivalent JSON can differ by whitespace or key order across
client versions, retries, or tests.

Raw-text fingerprints would treat those equivalent payloads as different
events, creating duplicate review candidates even though no meaningful hook
metadata changed.

## Decision

When hook payload text parses as JSON, compute the fingerprint from canonical
JSON with sorted keys and compact separators. When payload text is not valid
JSON, keep raw-text fingerprinting.

Render the fingerprint mode in source metadata and the review body so reviewers
can tell whether a hook event was deduplicated by canonical JSON or raw text.

## Consequences

- Equivalent JSON hook payloads reuse the same inbox candidate even if key order
  or whitespace changes.
- Non-JSON hook payloads retain raw-text fingerprint behavior.
- Reviewers can inspect `fingerprint_mode` when investigating hook retries.

## Limitations

- JSON values that differ semantically still produce different fingerprints.
- Numeric and Unicode normalization follow Python JSON parsing and encoding
  behavior.
- Existing hook files created with raw JSON-text fingerprints are not renamed.

## Future Work

- Add a hook retry summary if reviewers need counts for repeated captures.
- Consider preserving a non-secret payload shape summary for canonical JSON
  payloads.
- Keep raw payload capture opt-in and secret-scanned.

## Dependencies

- ADR 0005 defines provider-aware hook capture.
- ADR 0006 defines managed hook instruction blocks.
- ADR 0141 defines hook event idempotency.

## References

- `scripts/hook_event.py`
- `docs/hooks.md`
- `tests/test_memory_tools.py`
