# ADR 0064: MCP Conflict Keep Resolution

Status: Accepted for the v2 draft.

## Context

The conflict review workflow detects duplicate, preference, project decision,
and restricted-memory conflicts. The CLI already supports two reviewed
resolution paths:

- `ai-dememory conflict resolve --id <id> --keep <memory-id>`
- `ai-dememory conflict resolve --id <id> --merge-proposal`

MCP clients only had `memory.conflict_merge_proposal`, so they could draft a
merge packet but could not record the simpler reviewed keep decision without
shelling out. That made Codex plugin workflows less complete and encouraged
using merge proposals even when a human had already decided which memory should
remain canonical.

## Decision

Expose `memory.conflict_keep` as an MCP tool.

The tool accepts:

- `id`
- `keep`
- `reviewer`

It calls the same reviewed conflict resolver as the CLI keep path and writes
only `.ai-dememory-ignore.toml`. Its structured receipt includes the ignore
file path, conflict id, kept memory id, recorded status, decision, reviewed
date, and `canonical_memory_updated: false`.

`memory.conflict_keep` does not edit, delete, supersede, archive, or promote
Markdown memory. It records review state only. Any canonical memory changes
still require explicit human-approved edits and the usual validation and secret
scan gates.

## Benefits

- Gives MCP clients parity with the CLI keep-resolution workflow.
- Avoids unnecessary merge proposal files when a reviewed keep decision is
  enough.
- Returns a receipt that makes the non-mutation boundary explicit.
- Keeps review state auditable in `.ai-dememory-ignore.toml`.

## Limitations

- The resolver records the requested kept id; it does not rewrite canonical
  Markdown to mark other memories superseded.
- The tool relies on the existing conflict id remaining stable across the
  current report inputs.
- It does not prove the kept memory is semantically better than the alternatives;
  that remains a human review judgment.

## Future Risks

- If conflict resolution grows richer states, the receipt may need a schema
  version or a more detailed action field.
- If clients add one-click conflict cleanup, they must keep this tool separate
  from any future canonical-memory mutation step.
- If conflict ids change because detection rules change, older keep decisions
  may need migration or stale-decision reporting.

## Dependencies

- ADR 0001 defines review and conflict workflows.
- ADR 0027 defines review modes and keeps durable/canonical writes human-gated.
- `scripts/review_memory.py` remains the shared CLI/MCP implementation for
  conflict review state.
