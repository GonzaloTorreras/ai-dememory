# ADR 0110: Release Evidence Recall Freshness

## Status

Accepted.

## Context

`ai-dememory recall-fixtures status` already reports whether recall fixtures
are seed-only, stale, or fresh. The v2 release evidence, however, did not expose
that quality signal. A release handoff could therefore show manual acceptance
blockers while omitting that recall quality still needed a reviewed promotion
from a real retrieval miss.

Adding this to `release-check --strict` would make every pull request fail until
reviewed recall-miss evidence exists. That would be too broad for ordinary CI
because a fresh checkout can be technically healthy while still lacking the
manual recall-review artifact needed for final release sign-off.

## Decision

Add `recall_fixture_freshness` to `ai-dememory release-evidence` JSON and
Markdown output.

When freshness reports `stale: true`, add a structured `release_blockers` entry
with id `recall_fixture_review`, kind `quality`, and the freshness payload as
the blocker item. Keep `release-check` as the automated repository-health gate;
final release readiness continues to be determined by `release-evidence`.

## Benefits

- Makes the recall-quality blocker visible in the same final handoff artifact
  as manual acceptance and automated readiness.
- Avoids hiding seed-only fixture state behind a separate command.
- Keeps CI useful for draft PRs while still preventing `release-evidence
  --strict` from passing without reviewed recall-quality evidence.

## Limitations

- The blocker does not create a recall miss or promote a fixture. Reviewers must
  still capture and review real retrieval misses.
- The freshness check is local to `quality/recall-fixtures.json`; it does not
  inspect external analytics or MCP client history.
- The evidence report can become stale after a reviewer promotes a new fixture.

## Future Risks

- If the project later adds a scheduled recall-review workflow, the freshness
  blocker should include the latest workflow run or report path.
- If release readiness starts querying GitHub status, recall freshness should
  remain a quality blocker rather than being merged into generic CI failures.
- If multiple fixture suites are added, the field should become a list keyed by
  suite name.

## Dependencies

- ADR 0017 defines reviewed recall miss promotion.
- ADR 0034 defines recall fixture freshness status.
- ADR 0050 defines structured release blockers.
- `scripts/recall_fixtures.py` remains the source of fixture freshness.
- `scripts/release_evidence.py` remains the final release readiness aggregator.
