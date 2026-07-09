# ADR 0152: Maintenance Conflict Review Summary

## Status

Accepted

## Context

Conflict review is already first-class through `ai-dememory review conflicts`
and MCP `memory.review_conflicts`, but routine maintenance status only surfaced
false-positive review due work. ADR 0147 left conflict-review follow-up counts
as future work.

Operators running daily or weekly maintenance need a compact signal that active
memory conflicts exist, without parsing the full conflict report or generating
merge proposals.

## Decision

Add a read-only `conflict_review` summary to:

- `ai-dememory maintenance status`
- MCP `memory.maintenance_status`
- daily and weekly generated maintenance reports
- package and Docker install-smoke maintenance status validation

The summary contains bounded counts and ids only:

- `available`
- `errors`
- `conflicts`
- `active_conflicts`
- `reviewed_conflicts`
- `active_ids`
- `status_counts`
- `category_counts`
- `canonical_memory_updated=false`

If memory validation prevents conflict detection, the summary returns
`available=false` with bounded errors instead of failing the broad maintenance
status view.

## Consequences

- Routine maintenance now shows conflict follow-up work alongside generated
  artifact, provider, and false-positive review status.
- MCP clients can show active conflict counts without reading the full conflict
  candidate payload.
- Installed and Docker smoke catch drift in the expanded maintenance status
  contract.

## Limitations

- The summary does not include excerpts or summaries from memories; reviewers
  still use `review conflicts` for detailed evidence.
- Conflict detection depends on valid canonical memory frontmatter.
- Active ids are bounded to keep status payloads compact.

## Future Work

- Include conflict-review counts in a future combined setup health report if one
  is added.
- Add reviewed conflict aging or due dates if conflict decisions need periodic
  re-review.
- Consider release evidence blockers only if active conflicts become a release
  policy concern.

## Dependencies

- ADR 0001 defines conflict review state in `.ai-dememory-ignore.toml`.
- ADR 0147 defines maintenance review summaries.
- ADR 0150 defines stale false-positive suppression maintenance summaries.

## References

- `scripts/maintenance.py`
- `scripts/review_memory.py`
- `mcp/server/memory_mcp.py`
- `scripts/install_smoke.py`
