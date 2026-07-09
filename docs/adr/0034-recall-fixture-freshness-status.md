# ADR 0034: Recall Fixture Freshness Status

## Status

Accepted for v2 draft.

## Context

The v2 quality plan requires recall fixtures to grow from reviewed real misses,
not only from initial seed examples. `ai-dememory recall-fixtures promote-miss`
already preserves provenance when a reviewer promotes a miss, but reviewers had
no quick way to see whether the current fixture set was seed-only, recently
promoted, or stale.

Making fixture freshness a hard release check would also be misleading for
draft PRs and fresh checkouts, because a real retrieval miss may not exist yet.
The system needs visibility for weekly review without pretending that synthetic
fixtures prove ongoing recall quality.

## Decision

Add `ai-dememory recall-fixtures status`.

The command reads `quality/recall-fixtures.json` and reports:

- total fixture count
- count of fixtures with `reviewed_at` provenance
- count of seed fixtures without reviewed promotion provenance
- latest `created_at` and `reviewed_at` dates
- days since the latest reviewed promotion
- whether reviewed promotions are missing or stale for a configurable freshness
  window

The command is read-only and exits zero by default. `--strict` exits nonzero
when there is no reviewed promotion or the latest reviewed promotion is older
than `--max-age-days`.

## Benefits

- Makes the weekly recall quality loop visible and auditable.
- Distinguishes seed fixtures from real reviewed miss promotions.
- Gives operators a strict mode for recurring review jobs without breaking
  draft PR automation.
- Keeps vector-search decisions tied to measured fixture history.

## Limitations

- Freshness does not prove the fixture set is representative.
- Seed-only repositories will report that reviewed promotion is needed until a
  real miss is captured and reviewed.
- The command does not generate misses, tune ranking, or decide whether a miss
  is important.

## Future Risks

- Teams may need fixture categories, owners, or per-project freshness windows.
- A strict weekly job can become noisy if a project has no meaningful misses for
  a long period.
- Future vector experiments may require richer trend reports, not only the
  latest reviewed promotion date.

## Dependencies

- Depends on ADR 0017 for reviewed recall miss promotion.
- Depends on `quality/recall-fixtures.json` remaining the canonical recall
  fixture source.
- Depends on `eval-recall` continuing to measure fixture pass/fail separately
  from fixture freshness.
