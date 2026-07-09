# ADR 0149: Stale False-Positive Suppression Audit

## Status

Accepted

## Context

False-positive suppressions are stored in `.ai-dememory-ignore.toml` using
deterministic finding ids. ADR 0146 made active suppressions report due status,
ADR 0147 surfaced due counts in maintenance, and ADR 0148 added a due-only
review filter.

Those views only cover findings currently emitted by the scanner. If a file is
removed, a line changes, or scanner rules change, an old ignored
false-positive id can remain in `.ai-dememory-ignore.toml` even though the
current scan no longer emits that id. Reviewers need a read-only way to find
those stale suppressions before deciding whether to remove them.

## Decision

Add a stale false-positive suppression audit:

- CLI: `ai-dememory review stale-false-positives`
- MCP: `memory.review_stale_false_positives`

The audit reads `.ai-dememory-ignore.toml`, compares ignored
`false_positives.<id>` sections with current scanner finding ids, and returns
ignored suppressions whose current finding no longer exists.

The audit writes only a generated report under `reports/` when the CLI report
command is used. It does not edit `.ai-dememory-ignore.toml`, canonical memory,
inbox files, or generated indexes.

## Consequences

- Reviewers can identify suppressions that may be obsolete after files or
  scanner rules change.
- MCP clients can show stale suppressions without running broader report
  parsing.
- The existing `false-positive unignore` command remains the explicit reviewed
  path for removing a stale suppression.

## Limitations

- A stale suppression is not automatically wrong; the underlying finding may
  have disappeared because content moved, was fixed, or scanner rules changed.
- The audit cannot reconstruct old redacted lines; it reports stored review
  metadata only.
- The audit only covers ignored false-positive suppressions, not conflict
  decisions.

## Future Work

- Add an MCP batch unignore proposal flow that still requires reviewer approval.
- Include stale suppression review in final manual acceptance evidence.

ADR 0150 later surfaces stale suppression counts in maintenance status and
reports.

## Dependencies

- ADR 0001 defines review state storage in `.ai-dememory-ignore.toml`.
- ADR 0081 defines false-positive unignore receipts.
- ADR 0146 defines false-positive due-status fields.
- ADR 0148 defines due-only false-positive filtering.

## References

- `scripts/review_memory.py`
- `mcp/server/memory_mcp.py`
- `docs/review-workflows.md`
