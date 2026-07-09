# ADR 0138: Provider Import Idempotency

## Status

Accepted

## Context

Daily maintenance can import enabled provider chat/session files into
`inbox/imports/<provider>/`. Without idempotency, the same provider file can
produce a fresh inbox candidate every scheduled run because candidate filenames
include timestamps.

ADR 0137 added provider import dry-run so users can preview candidates before
writing them. That preview is useful before a first import, but scheduled
imports also need repeat-run behavior that avoids creating duplicate review
work.

## Decision

Compute a stable provider import fingerprint from the source file path and raw
decoded text before rendering Markdown. Include that fingerprint in the
candidate filename and rendered source metadata.

Before writing or previewing a provider import candidate, check
`inbox/imports/<provider>/` for an existing candidate with the same slug and
fingerprint. If one exists, skip the candidate with reason `already imported`
and return the existing inbox path. Dry-run mode follows the same duplicate
check and does not return duplicate `would_write` paths.

## Consequences

- Daily or weekly scheduled imports do not repeatedly create the same provider
  review candidate.
- Dry-run previews match repeat-run behavior more closely.
- Reviewers can trace duplicate skips to the existing inbox candidate path.
- The stable fingerprint is local metadata and does not require generated
  SQLite state.

## Limitations

- The fingerprint uses the source file path, so moving a provider file can
  create a new candidate even if the text is unchanged.
- The duplicate check is limited to the provider inbox and does not compare
  across different providers or explicit captures.
- Existing candidates created before this fingerprint filename convention may
  not be detected as duplicates.

## Future Work

- Add an optional import manifest if cross-provider or moved-file deduplication
  becomes necessary.
- Consider content-only deduplication for providers that frequently move or
  rotate export files.
- Add review tooling to merge or dismiss historical duplicate import
  candidates.

## Dependencies

- ADR 0136 defines provider readiness in maintenance status.
- ADR 0137 defines provider import dry-run behavior.
- `scripts/provider_import.py` owns provider import rendering and inbox writes.

## References

- `scripts/provider_import.py`
- `scripts/maintenance.py`
- `tests/test_memory_tools.py`
