# ADR 0147: Maintenance Review Due Summary

## Status

Accepted

## Context

ADR 0146 made false-positive suppression review-after dates machine-readable
through `review_due` and `review_after_status`. The maintenance loop already
reports provider readiness, generated artifact state, lifecycle artifacts, and
recent reports, but it did not summarize review suppressions that had become
due.

That meant scheduled or manual maintenance could finish without showing that a
reviewed secret-scan suppression needed a follow-up human review.

## Decision

Add a read-only `review_due` summary to:

- `ai-dememory maintenance status`
- MCP `memory.maintenance_status`
- generated daily and weekly maintenance reports
- package and Docker install-smoke maintenance status validation

The summary contains counts and bounded due ids only:

- `false_positive_findings`
- `active_findings`
- `ignored_findings`
- `due_findings`
- `due_ids`
- `status_counts`
- `canonical_memory_updated=false`

Maintenance status does not include redacted finding lines or secret-like
content. The summary is derived from current secret-scan findings and
`.ai-dememory-ignore.toml`; it does not mutate canonical memory.

## Consequences

- Routine maintenance can surface expired false-positive suppressions.
- MCP clients and plugin workflows can show review work without calling the
  broader false-positive review listing.
- Installed and Docker smoke now verify that maintenance status includes review
  due visibility.

## Limitations

- The summary depends on current secret-scan findings. If a finding disappears,
  its old suppression is not counted in current due totals.
- Due ids are bounded to keep broad status payloads compact.
- The summary does not notify users or automatically reopen suppressions.
- Maintenance runs still fail on current secret-scan findings according to the
  existing safety boundary; this summary does not bypass secret scanning.

## Future Work

ADR 0149 later adds the dedicated stale-suppression audit for suppressions
whose findings no longer exist. ADR 0150 surfaces stale suppression counts in
maintenance status. ADR 0151 later includes the same review summary in
scheduler status. ADR 0152 later adds a maintenance conflict-review summary.

## Dependencies

- ADR 0055 defines generated artifact visibility in maintenance status.
- ADR 0136 defines provider readiness in maintenance status.
- ADR 0146 defines false-positive due-status fields.

## References

- `scripts/maintenance.py`
- `scripts/review_memory.py`
- `mcp/server/memory_mcp.py`
- `scripts/install_smoke.py`
