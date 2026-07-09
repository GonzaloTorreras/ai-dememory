# ADR 0148: False-Positive Due-Only Filter

## Status

Accepted

## Context

ADR 0146 added `review_due` and `review_after_status` to false-positive review
records. ADR 0147 surfaced due counts in maintenance status. Reviewers still
had to generate or inspect the full false-positive report to isolate the
suppressed findings whose review-after dates were due.

Large secret-scan reports can contain active findings, future suppressions, and
already reviewed suppressions. A focused due-only view makes the recurring
review loop easier without changing the underlying suppression state.

## Decision

Add a due-only filter to false-positive review surfaces:

- CLI: `ai-dememory review false-positives --due-only`
- MCP: `memory.review_false_positives` with `due_only=true`

The filter returns only ignored findings with `review_due=true`. JSON responses
include `due_only` and `returned_count` so clients can confirm which view was
requested. The generated Markdown report includes `filter: due_only`.

The filter is read-only. It does not edit `.ai-dememory-ignore.toml`, canonical
memory, inbox files, or generated indexes.

## Consequences

- Weekly review can focus on suppressions requiring immediate human follow-up.
- MCP clients can render a compact due-review queue without post-filtering.
- The full report remains the default so existing workflows keep seeing active
  findings and scheduled suppressions.

## Limitations

- The filter depends on the current secret-scan result set. Stale suppressions
  whose findings disappeared are not returned.
- The filter does not notify users or mark suppressions as reviewed.
- The due decision still uses the local date where the command runs.

## Future Work

- Add a stale-suppression audit for ignored ids no longer present in current
  scan results.
- Add equivalent due-only filtering for conflict review if conflict decisions
  gain review-after dates.
- Add a maintenance command that writes only due review reports.

## Dependencies

- ADR 0124 defines review report path guards.
- ADR 0146 defines false-positive due-status fields.
- ADR 0147 defines maintenance review due summaries.

## References

- `scripts/review_memory.py`
- `mcp/server/memory_mcp.py`
- `docs/review-workflows.md`
