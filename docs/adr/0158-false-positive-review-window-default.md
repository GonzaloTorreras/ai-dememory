# ADR 0158: False-Positive Review Window Default

Status: Accepted

## Context

False-positive suppressions are reviewed audit records in
`.ai-dememory-ignore.toml`. The review workflow already supports
`review_after` dates, `review_due`, due-only reports, stale suppression audits,
and MCP receipts. However, callers had to pass `--review-after-days` or
`review_after_days` every time they ignored a finding.

The v2 configuration direction includes a `[false_positives]` section with a
default review window. Without using that setting, local vault policy and MCP
behavior could drift.

## Decision

Add a vault-local default false-positive review window:

```toml
[false_positives]
review_after_days = 90
```

`ai-dememory false-positive ignore` and MCP `memory.false_positive_ignore`
use this value when the caller omits an explicit review window. Explicit CLI
and MCP arguments still take precedence. Missing or invalid config falls back to
the built-in 90-day default, and values are clamped to at least one day.

## Benefits

- Reviewed suppressions consistently get revalidation dates without requiring
  every client to pass a flag.
- MCP clients can rely on vault policy while still overriding the window for a
  specific reviewed finding.
- New vaults document the expected review cadence in versioned config.

## Limitations

- Existing suppressions without `review_after` are not rewritten.
- The default does not prove a human will perform the review when it becomes
  due; it only makes due work visible to reports and maintenance summaries.
- The config parser intentionally supports simple scalar values only.

## Future Work

- Add setup-health visibility for configured review windows if users need
  first-run policy summaries.
- Add separate defaults per finding severity if real suppressions need
  different cadences.
- Consider a migration helper for old suppressions without `review_after`.

## Dependencies

- ADR 0146 defines false-positive due-status fields.
- ADR 0148 defines due-only false-positive filtering.
- ADR 0149 defines stale false-positive suppression audits.
- `scripts/review_memory.py` owns false-positive suppression writes.
