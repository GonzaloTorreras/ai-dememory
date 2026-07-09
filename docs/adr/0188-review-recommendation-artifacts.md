# ADR 0188: Review Recommendation Artifacts

Status: Accepted

## Context

The v2 improvement plan includes configurable LLM-assisted cleanup. Earlier
slices added review modes, policy defaults, conflict and false-positive review
state, MCP review planning, and explicit human-gated conflict actions.

One gap remained: when an LLM or MCP client recommends an outcome, there was no
durable audit artifact for that recommendation unless a human immediately
accepted it. That weakens assisted review because rationale, confidence, and
policy context can be lost before the reviewer decides.

## Decision

Add advisory review recommendation artifacts.

The CLI command is:

```bash
ai-dememory review recommendation \
  --kind conflict \
  --target-id conf_... \
  --recommendation keep_memory \
  --rationale "Keep the newer policy after human review." \
  --recommended-by "Local LLM"
```

MCP exposes the same writer as `memory.review_recommendation`.

Recommendations are written under `inbox/review-recommendations/`. Each artifact
records:

- recommendation id, kind, target id, recommendation action, rationale,
  confidence, evidence, recommender, and creation time;
- active review mode and policy snapshot;
- whether the recommendation is allowed by the active mode;
- `policy_violation=true` when a recommendation exceeds the mode; and
- hard safety flags: `requires_human_approval=true`,
  `applies_review_decision=false`, and `writes_canonical_memory=false`.

The writer secret-scans rendered artifacts before writing. It never edits
`.ai-dememory-ignore.toml`, never writes conflict merge proposals, never
promotes memory, and never mutates canonical memory.

## Benefits

- LLM/client review suggestions become auditable even when not accepted.
- Reviewers can see whether a suggestion matched the active review mode.
- Strict-mode policy violations can be recorded without applying them.
- MCP clients get a safe way to persist review rationale before a human action.

## Limitations

- The artifact is not approval and does not prove human review.
- The command does not validate that a target id currently exists; it can record
  recommendations for stale or external review targets.
- Recommendation actions are coarse enums, not full typed resolution objects.
- Recommendation files are append-only inbox artifacts and are not automatically
  reconciled with later accepted or rejected outcomes.

## Future Work

- Add stricter target validation for conflict and false-positive ids when the
  current scanner state is available.
- Add optional expiration or archival of stale recommendation artifacts.

## Dependencies

- ADR 0002 defines configurable review modes.
- ADR 0027 defines canonical review mode names.
- ADR 0161 defines normalized review policy defaults.
- ADR 0162 defines review enabled-policy enforcement.
- ADR 0082 defines MCP review-mode configuration.
- ADR 0190 defines links from accepted review outcomes back to recommendation
  ids.
- `scripts/review_memory.py` owns review planning, recommendation capture, and
  review state writes.
- `mcp/server/memory_mcp.py` exposes the shared recommendation writer to MCP
  clients.
