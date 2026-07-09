# ADR 0017: Recall Fixture Promotion

## Status

Accepted for v2 draft.

## Context

The v2 quality plan requires recall quality to be measured before adding vector
search or changing retrieval architecture. Earlier work added
`ai-dememory eval-recall` and `ai-dememory capture-miss`, but the workflow
still had a manual gap: a reviewer had to edit `quality/recall-fixtures.json`
by hand after validating a miss from `inbox/recall-feedback/`.

Hand editing fixtures is possible, but it is easy to lose reviewer provenance,
create duplicate fixture ids, or accidentally add a fixture for a memory id that
does not exist.

## Decision

Add `ai-dememory recall-fixtures promote-miss`, backed by
`scripts/recall_fixtures.py`.

The command:

- reads one Markdown miss file from `inbox/recall-feedback/`
- requires a human `--reviewed-by` value
- resolves `expected_id` directly or from `expected_path`
- verifies the expected memory id exists in canonical memory
- appends a fixture to `quality/recall-fixtures.json`
- records `source_ref`, `created_at`, `reviewed_by`, and `reviewed_at`
- rejects duplicate fixture ids and duplicate query/expected-id coverage
- secret-scans the fixture before writing it
- validates that the promoted fixture passes against the current search index
- marks the source miss as `status: promoted` with review provenance and the
  promoted fixture id

## Benefits

- Makes the miss-to-fixture workflow repeatable and reviewable.
- Preserves reviewer provenance on quality fixtures.
- Keeps vector-search decisions tied to curated, measured failures.
- Reduces accidental fixture drift while keeping Markdown and JSON as the
  canonical quality source.
- Keeps weekly recall review plans focused on unresolved miss files.

## Limitations

- The command does not decide whether a miss is important. A human still reviews
  the miss before promotion.
- The command does not tune aliases, metadata, or search ranking.
- It requires the generated search index to exist before promotion can prove the
  fixture passes.
- It does not add separate commands for rejected or dismissed misses.

## Future Risks

- Larger fixture sets may need categories, owner fields, or expiry dates.
- Reviewers may overfit fixtures to current wording if misses are promoted too
  aggressively.
- Future semantic/vector experiments will need backend-specific comparison
  reports, not only fixture promotion.
