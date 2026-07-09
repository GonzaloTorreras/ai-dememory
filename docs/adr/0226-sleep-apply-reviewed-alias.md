# ADR 0226: Sleep Apply-Reviewed Alias

Status: Accepted

## Context

The safe sleep consolidation roadmap named `ai-dememory sleep --apply-reviewed`
alongside `sleep --dry-run` and `sleep --propose`. ADR 0225 added the dry-run
and propose aliases, but the reviewed alias still only existed as the canonical
subcommand `ai-dememory sleep apply-reviewed`.

Users following the roadmap should be able to use the named alias without
getting a parser error.

## Decision

Add top-level `ai-dememory sleep --apply-reviewed` as a compatibility alias for
the existing reviewed packet writer.

The alias:

- requires either `--id <sleep_id>` or `--all`;
- rejects combining `--id` and `--all`;
- writes only sleep review packets under `inbox/sleep-consolidation/`;
- reports `writes_canonical_memory=false` and `deletes_files=false` in JSON
  output; and
- keeps `ai-dememory sleep apply-reviewed` as the canonical explicit
  subcommand.

## Benefits

- The CLI now supports all sleep commands named in the v2 roadmap.
- Scripts and docs can use either roadmap-style flags or canonical
  subcommands.
- Safety behavior remains identical to the existing packet writer.

## Limitations

- The alias does not verify that an external human actually reviewed the
  candidate before packet generation.
- It writes review packets immediately once a scope is provided.
- It does not apply canonical memory edits, archive memories, or resolve
  conflicts.

## Future Risks

- If sleep packets gain explicit review metadata, the alias should require or
  accept those fields without changing canonical memory.
- If a future compaction workflow applies changes, it must use a separate
  command so this alias remains inbox-only.
- If MCP clients need equivalent wording, document it as a client-facing label
  over `memory.sleep_apply_reviewed` rather than adding duplicate MCP tools.

## Dependencies

- ADR 0004 defines safe sleep consolidation.
- ADR 0225 defines dry-run and propose aliases.
- `scripts/sleep_consolidation.py` owns sleep CLI behavior.
