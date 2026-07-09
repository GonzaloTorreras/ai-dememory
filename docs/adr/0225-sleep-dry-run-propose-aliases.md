# ADR 0225: Sleep Dry-Run And Propose Aliases

Status: Accepted

## Context

The v2 improvement handoff described safe sleep consolidation with commands
such as `ai-dememory sleep --dry-run` and `ai-dememory sleep --propose`.
The implemented CLI already had the safer explicit subcommands
`ai-dememory sleep plan` and `ai-dememory sleep apply-reviewed`, but the
roadmap aliases did not work.

Users following the handoff should get the safe existing behavior rather than a
parser error.

## Decision

Add top-level sleep aliases:

- `ai-dememory sleep --dry-run` previews the sleep plan without writing
  reports or packets.
- `ai-dememory sleep --dry-run --json` emits the same no-write preview as
  structured JSON with `writes_files=false`.
- `ai-dememory sleep --propose` writes sleep review packets to
  `inbox/sleep-consolidation/`.
- `ai-dememory sleep --propose --id <sleep_id> --json` writes selected review
  packets and reports `writes_canonical_memory=false`.

Existing subcommands remain canonical for explicit workflows:
`sleep plan`, `sleep plan --report-path`, `sleep plan --json-report-path`, and
`sleep apply-reviewed`.

The aliases do not edit, archive, supersede, promote, or delete canonical
memory.

## Benefits

- The CLI now matches the roadmap and handoff language.
- Plugins and scripts can request a no-write sleep preview with a short command.
- Users can generate review packets with roadmap terminology while preserving
  the existing inbox-only safety boundary.

## Limitations

- `--dry-run` does not write the generated Markdown or JSON reports; callers
  that need report files must still use `sleep plan`.
- `--propose` writes review packets immediately; it does not mean a human has
  approved any canonical memory change.
- The aliases do not add semantic clustering or automatic compaction.

## Future Risks

- If sleep proposals gain explicit human review metadata, the alias payloads
  should report that metadata separately from packet generation.
- If automatic compaction is added later, it must use a new explicit command and
  not change these aliases to mutate canonical memory.
- If MCP clients need the same alias names, add them as documentation labels
  over the existing `memory.sleep_plan` and `memory.sleep_apply_reviewed`
  tools rather than duplicating MCP tools.

## Dependencies

- ADR 0004 defines the safe sleep consolidation workflow.
- ADR 0122 defines generated sleep report path guards.
- `scripts/sleep_consolidation.py` owns CLI sleep planning and packet writing.
