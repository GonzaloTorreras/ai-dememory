# ADR 0080: Manual Acceptance Evidence Templates

## Status

Accepted.

## Context

Manual v2 acceptance checks need reviewed proof before release, but reviewers
also need a safe way to preview what evidence is expected. The existing
`acceptance plan` command gives next actions across all items, while
`acceptance record` writes reviewed evidence under `inbox/release-acceptance/`.
There was no single-item, read-only artifact that could be copied into a review
comment or local note before the check was actually completed.

## Decision

Add `ai-dememory acceptance template --item <id> --json` and the MCP tool
`memory.acceptance_template`.

The template includes the acceptance item, suggested artifacts, review-note
placeholders, and the exact `ai-dememory acceptance record` command to run
after a human reviewer has real evidence. The CLI and MCP tool report
`mutates_system=false`, `writes_files=false`, and `records_evidence=false`.

## Benefits

- Reviewers can prepare evidence notes without creating false acceptance
  records.
- MCP clients can surface a single manual acceptance checklist item without
  granting write behavior.
- Release handoffs can point to a concrete record command while keeping the
  proof boundary clear.

## Limitations

- A template is not acceptance evidence.
- The command does not inspect external MCP clients, Docker, Obsidian, TestPyPI,
  or provider files.
- The reviewer still has to run `acceptance record` after completing the manual
  check.

## Future Risks

- If acceptance items change, stale copied templates may remain outside the
  repository.
- If clients display the Markdown template without the `records_evidence=false`
  fields, users may confuse guidance with proof.
- More elaborate evidence workflows may eventually need attachments or signed
  reviewer attestations.

## Dependencies

- `scripts/manual_acceptance.py` remains the source of truth for acceptance
  items and suggested artifacts.
- `mcp/server/memory_mcp.py` exposes the read-only MCP wrapper.
- `docs/release-v2-checklist.md` and MCP inventory checks guard the documented
  surface.
