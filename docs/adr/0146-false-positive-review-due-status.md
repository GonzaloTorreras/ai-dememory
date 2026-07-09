# ADR 0146: False-Positive Review Due Status

## Status

Accepted

## Context

False-positive suppressions can include `review_after` dates so reviewed
secret-scan suppressions do not become permanent by accident. The stored date
was visible, but reports and MCP receipts did not classify whether the
suppression was still scheduled, already due, missing a schedule, or malformed.

Reviewers therefore had to interpret dates manually, and MCP clients could not
reliably flag suppressions that needed another human review.

## Decision

Add derived due-status fields to false-positive review records:

- `review_due`: boolean, true when an ignored finding should be reviewed now.
- `review_after_status`: one of `not_ignored`, `not_scheduled`, `scheduled`,
  `due`, or `invalid`.

`ai-dememory review false-positives` includes the due count in the report
summary and prints the status for ignored findings. MCP
`memory.review_false_positives`, `memory.false_positive_ignore`, and
`memory.false_positive_unignore` return the same derived fields.

The fields are derived from `.ai-dememory-ignore.toml`; they do not change the
stored suppression format and do not mutate canonical memory.

## Consequences

- Review reports can highlight expired suppressions without requiring manual
  date comparison.
- MCP clients and plugin workflows can surface suppressions that need review.
- Invalid `review_after` values become visible as due instead of being silently
  treated as safe.

## Limitations

- The due status is computed using the local date where the command runs.
- The diagnostic does not notify users or create recurring review jobs.
- Existing suppressions without `review_after` are classified as
  `not_scheduled`, not as automatically due.

## Future Work

- Add a dedicated `review false-positives --due-only` filter if reports become
  large.
- Include due suppression counts in maintenance summaries.
- Add acceptance evidence for reviewing one expired suppression before v2 final
  release readiness.

## Dependencies

- ADR 0001 defines review and conflict workflows.
- ADR 0081 defines false-positive unignore receipts.
- ADR 0086 exposes review receipt tools through the plugin.
- ADR 0124 defines review report path guards.

## References

- `scripts/review_memory.py`
- `mcp/server/memory_mcp.py`
- `docs/review-workflows.md`
