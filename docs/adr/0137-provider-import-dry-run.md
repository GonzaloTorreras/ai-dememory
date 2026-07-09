# ADR 0137: Provider Import Dry Run

## Status

Accepted

## Context

Provider readiness can show whether a configured chat/session folder is ready
for import, but the import command previously wrote review candidates
immediately. Users need a preview step before importing local Codex, Claude,
Cursor, Windsurf, or ChatGPT provider files into `inbox/imports/`.

This matters most before enabling scheduled maintenance. A provider may be
configured and enabled, yet still contain many files, unreadable files, empty
files, or secret-like content that would be skipped. The setup path needs a
reviewable preflight that reads provider files but does not write inbox files.

## Decision

Add `--dry-run` to `ai-dememory import-chats`. In dry-run mode the command
discovers, reads, renders, and scans provider candidates, then returns
`would_write` paths without creating `inbox/imports/` or writing candidate
Markdown files.

Expose the same behavior through MCP `memory.import_chats` with
`dry_run=true`. Keep the tool annotated as write-capable because the same tool
can write when `dry_run` is false.

Add `import_dry_run_command` to provider setup plans so first-run setup and
Codex plugin workflows can show a reviewable preview command before the real
import command.

## Consequences

- Users can preview provider import candidates before writing inbox files.
- Setup and maintenance planning can recommend a safe preflight after provider
  configuration and before scheduled imports.
- Runtime smoke coverage verifies that MCP dry-run returns `would_write` and
  does not report candidate writes.

## Limitations

- Dry-run still reads provider chat/session files so it is not a provider
  privacy no-op.
- Preview paths include the generated timestamp and are not stable promises
  about the exact filename a later non-dry-run import will write.
- Dry-run does not summarize candidate contents; it only returns counts,
  skipped reasons, and predicted inbox paths.

## Future Work

- Add provider-specific summary counts to scheduler setup reports if reviewers
  need permanent pre-run evidence.
- Add bounded content previews only after a separate privacy review.
- Use recall and import feedback to decide whether provider import ranking or
  deduplication needs additional scoring.

## Dependencies

- ADR 0067 defines read-only MCP provider status.
- ADR 0078 defines provider setup planning.
- ADR 0136 defines provider readiness in maintenance status.

## References

- `scripts/provider_import.py`
- `mcp/server/memory_mcp.py`
- `scripts/mcp_runtime_smoke.py`
