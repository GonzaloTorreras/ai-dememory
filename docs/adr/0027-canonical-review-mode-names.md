# ADR 0027: Canonical Review Mode Names

## Status

Accepted for v2 draft.

## Context

The v2 improvement plan names four review modes: `strict`, `balanced`,
`assisted`, and `autonomous_proposals`. The first implementation exposed
`strict`, `assisted`, and `batch`. That made the tool usable, but it drifted
from the documented setup direction and left no middle ground between strict
review and full assisted merge-proposal drafting.

Changing mode names can break existing vault config, so the migration needs a
compatibility path.

## Decision

Use the planned mode names as the canonical review policy surface:

- `strict`
- `balanced`
- `assisted`
- `autonomous_proposals`

Keep `batch` as a legacy alias for `autonomous_proposals`. When a user runs
`ai-dememory review configure-mode --mode batch`, the config is written back
with `mode = "autonomous_proposals"`.

Add `allow_autonomous_inbox_proposals` to review policy output and vault
templates so clients can distinguish inbox-only autonomous proposal handling
from canonical-memory writes.

## Benefits

- Aligns CLI, MCP, docs, and templates with the v2 plan.
- Preserves existing `batch` vaults without keeping `batch` as a first-class
  mode.
- Makes `balanced` available for recommendation-only review sessions.
- Keeps every durable and canonical memory mutation human-review gated.

## Limitations

- The mode system still provides local policy guidance; clients can ignore the
  guidance unless they enforce it.
- `autonomous_proposals` only describes low-risk inbox proposal handling. It
  does not add automatic durable promotion or canonical-memory mutation.
- Custom user-defined modes remain deferred.

## Future Risks

- If clients add richer approval UX, mode flags may need finer-grained MCP
  annotations.
- Existing documentation or saved snippets may still mention `batch`; the alias
  should remain until v2 adoption shows it is safe to remove.
- If autonomous inbox cleanup becomes executable rather than advisory, it will
  need separate tests and stronger path-boundary checks.
