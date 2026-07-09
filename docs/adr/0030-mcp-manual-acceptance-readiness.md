# ADR 0030: MCP Manual Acceptance Readiness

## Status

Accepted for v2 draft.

## Context

Manual release acceptance is recorded with `ai-dememory acceptance record` and
verified with `ai-dememory acceptance verify`. MCP clients could inspect
automated maintenance, scheduling, and review surfaces, but could not directly
ask whether manual acceptance was complete.

Release-oriented Codex plugin workflows need a read-only way to surface the
same readiness state without shelling out or granting MCP write access to
manual evidence records.

## Decision

Expose two read-only MCP tools:

- `memory.acceptance_status` returns the canonical manual acceptance items,
  completion booleans, and reviewed evidence records.
- `memory.acceptance_verify` returns the same completion summary as
  `ai-dememory acceptance verify --json`, but as structured MCP output.

Both tools only read `inbox/release-acceptance/`. They do not record evidence,
change release state, run external clients, or treat blocked evidence as
completion.

Reviewed manual evidence remains append-only CLI workflow data. Humans still
record proof with `ai-dememory acceptance record`.

## Benefits

- Lets MCP clients and Codex plugin skills report release readiness without
  spawning a shell.
- Keeps evidence recording explicit and review-first.
- Aligns MCP runtime smoke with the release checklist and release evidence
  gates.
- Preserves the distinction between automated readiness and manual acceptance.

## Limitations

- The tools trust reviewed Markdown evidence; they do not independently run
  real MCP clients, Docker, Obsidian, provider imports, or TestPyPI.
- Incomplete acceptance is returned as structured data, not an MCP tool error.
- The MCP surface intentionally cannot create or modify acceptance records.

## Future Risks

- If MCP clients start gating releases automatically, the verification output
  may need stronger provenance or reviewer identity metadata.
- If manual acceptance item ids change, the MCP output and historical records
  may need an explicit migration.
