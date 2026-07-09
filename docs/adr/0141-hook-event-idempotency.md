# ADR 0141: Hook Event Idempotency

## Status

Accepted

## Context

Codex and Claude hooks can capture small session-event metadata under
`inbox/session-events/`. Hooks are optional and review-first, but they may fire
repeatedly for the same event and payload during retries, client restarts, or
manual testing.

Before this decision, hook event filenames included timestamps. A repeated hook
payload could therefore create duplicate inbox candidates even though the
payload digest was already part of the filename and rendered body.

## Decision

Treat the payload SHA-256 prefix as the stable hook event fingerprint. Before
writing a hook event candidate, check `inbox/session-events/` for an existing
file with the same provider, event, and fingerprint. If one exists, return that
path instead of writing a duplicate file.

Include the fingerprint in rendered source metadata so reviewers can connect
the returned path, filename, and payload digest.

## Consequences

- Repeated hook captures for the same provider, event, and payload reuse the
  existing inbox candidate.
- Hook retries remain review-first without creating noisy duplicate files.
- The behavior aligns hook captures with provider import and git lesson
  idempotency.

## Limitations

- Different payloads for the same event still create separate candidates.
- The fingerprint is based on raw payload text, so semantically identical JSON
  with different formatting is treated as a different event.
- Existing hook candidates created before this filename pattern may not be
  deduplicated.

## Future Work

- Add JSON canonicalization if hook clients produce noisy formatting changes.
- Add a bounded hook-capture status report if reviewers need aggregate retry
  counts.
- Consider exposing a structured skip receipt if hook capture gains an MCP write
  tool.

## Dependencies

- ADR 0005 defines provider-aware hook capture.
- ADR 0006 defines managed hook instruction blocks.
- ADR 0138 and ADR 0140 define idempotency patterns for other inbox captures.

## References

- `scripts/hook_event.py`
- `docs/hooks.md`
- `tests/test_memory_tools.py`
