# ADR 0246: Clean Recall Eval Release Gate

## Status

Accepted.

## Context

Recall fixture freshness tracks whether real retrieval misses have been
reviewed and promoted into `quality/recall-fixtures.json`. That is useful for
weekly quality work, but it can block a package release indefinitely when there
are no real misses to promote and the current recall evaluation already passes.

The release owner should not fabricate a miss or pollute durable quality data
only to satisfy a freshness counter.

## Decision

Keep `recall_fixture_freshness` and `recall_fixture_review_plan` visible in
release evidence, but make `recall_fixture_review` a release blocker only when:

- pending or invalid recall miss files exist;
- current recall evaluation is unavailable; or
- current recall evaluation has failures.

When recall eval is available, all fixture cases pass, and there are no pending
or invalid miss files, stale seed-only provenance remains review evidence but
does not block package release readiness.

## Consequences

- Release evidence still shows seed-only or stale recall provenance.
- Package release readiness no longer depends on creating a synthetic miss.
- Real recall misses still need the existing review and promotion flow.
- Vector experiment review remains separately gated by measured recall failures.

## Limitations

- This does not replace weekly recall review.
- A tiny fixture set can still pass while missing broader real-world search
  cases; future fixture expansion remains important.
- If recall eval is unavailable, release readiness stays conservative.

## Future Work

- Add more public/non-secret recall fixtures before PyPI if real usage uncovers
  weak search cases.
- Consider recording explicit recall-review acceptance evidence if the project
  later needs reviewer identity separate from automated eval output.

## Dependencies

- ADR 0110 defines recall fixture freshness evidence.
- ADR 0111 defines the recall review plan payload.
- ADR 0130 defines recall miss candidate checks.
- ADR 0245 defines target-specific publish readiness.
- `scripts/release_evidence.py` owns release blocker synthesis.
