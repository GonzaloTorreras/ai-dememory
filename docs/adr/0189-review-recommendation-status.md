# ADR 0189: Review Recommendation Status

Status: Accepted

## Context

ADR 0188 added advisory review recommendation artifacts under
`inbox/review-recommendations/`. Those artifacts let an LLM or MCP client record
review rationale without applying false-positive suppressions, conflict
decisions, promotions, or canonical memory edits.

After recommendations can be captured, reviewers need a safe queue view. Reading
the queue must not become an approval path, and malformed artifacts must not
hide valid pending recommendations.

## Decision

Add a read-only recommendation status surface.

The CLI command is:

```bash
ai-dememory review recommendations --json
```

It accepts `--kind <kind>` and `--policy-violations-only` filters. MCP exposes
the same read model as `memory.review_recommendations`.

The response includes:

- pending recommendation counts;
- policy-violation and allowed recommendation counts;
- malformed artifact counts and parse errors;
- the latest recommendation timestamp;
- per-artifact metadata, including recommendation id, kind, target id,
  recommender, confidence, evidence, review mode, and safety flags; and
- explicit read-only flags: `mutates_system=false`, `writes_files=false`,
  `applies_review_decisions=false`, and `writes_canonical_memory=false`.

Secret-like metadata is redacted before it is returned. Malformed recommendation
files are listed separately instead of failing the entire queue.

## Benefits

- Reviewers can inspect pending LLM/client recommendations before deciding what
  explicit review command to run.
- Policy-violation suggestions are easy to triage without applying them.
- MCP clients get a stable read-only queue status tool.
- Invalid artifacts become visible without blocking valid recommendation
  review.

## Limitations

- The status command does not approve, reject, archive, or reconcile
  recommendations.
- It does not prove that the target id still exists.
- It does not link accepted outcomes back to recommendation ids.
- It reports artifact metadata only; reviewers still need the source reports or
  canonical memories before taking action.

## Future Work

- Add reviewed archive or stale recommendation cleanup after the approval model
  is documented.
- Validate known conflict and false-positive target ids when the current review
  state is available.

## Dependencies

- ADR 0188 defines advisory recommendation artifacts.
- ADR 0190 defines links from accepted review outcomes back to recommendation
  ids.
- ADR 0002 defines configurable review modes.
- ADR 0162 defines enabled review-policy enforcement.
- `scripts/review_memory.py` owns recommendation parsing and read-only status.
- `mcp/server/memory_mcp.py` exposes `memory.review_recommendations`.
