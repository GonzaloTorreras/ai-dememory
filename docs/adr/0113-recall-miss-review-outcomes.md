# ADR 0113: Recall Miss Review Outcomes

## Status

Accepted.

## Context

ADR 0112 made recall promotion close the source miss with `status: promoted`
and taught the weekly review plan to ignore resolved statuses: `promoted`,
`rejected`, and `dismissed`.

That left a review workflow gap. Reviewers could promote validated misses, but
invalid, duplicate, obsolete, or no-longer-reproducible misses still required
manual frontmatter edits to leave the pending queue. Manual edits made MCP and
plugin workflows weaker, and they made it harder to keep reviewer provenance
consistent.

## Decision

Add reviewed recall miss outcome recording:

- CLI: `ai-dememory recall-fixtures review-miss`
- MCP: `memory.recall_miss_review`

The operation accepts a miss path under `inbox/recall-feedback/`, a reviewed
status of `rejected` or `dismissed`, a reviewer, and a reason. It secret-scans
review metadata, rejects already-resolved misses, and updates only the source
miss frontmatter:

- `status`
- `reviewed_by`
- `reviewed_at`
- `review_reason`

The MCP receipt returns the path, status, reviewer metadata, reason, and
explicit `fixture_updated=false` and `canonical_memory_updated=false` flags.

## Benefits

- Lets weekly recall review close invalid or noisy misses without hand-editing
  YAML.
- Keeps review plans focused on unresolved misses.
- Gives MCP clients and the Codex plugin the same review outcome path as the
  CLI.
- Preserves reviewer provenance while keeping fixture promotion separate.

## Limitations

- Rejecting or dismissing a miss does not make recall fixtures fresh; only a
  reviewed promotion adds quality evidence to `quality/recall-fixtures.json`.
- The command does not delete recall miss files or archive them.
- The reason is free text, so it records reviewer intent but does not enforce a
  controlled taxonomy of rejection causes.

## Future Risks

- If recall miss queues grow large, resolved miss files may need an archive
  command or retention policy.
- If release evidence starts distinguishing rejected from dismissed misses, the
  receipt may need a stricter reason enum.
- If fixture suites are split by domain, review outcomes may need suite context
  to explain why a miss was rejected for a specific suite.

## Dependencies

- ADR 0017 defines recall fixture promotion.
- ADR 0045 defines recall fixture review planning.
- ADR 0112 defines source-miss closure for successful promotion.
- `scripts/recall_fixtures.py` owns recall miss review state.
- `mcp/server/memory_mcp.py` exposes the reviewed MCP receipt.
