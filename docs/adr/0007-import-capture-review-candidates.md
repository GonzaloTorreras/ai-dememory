# ADR 0007: Import And Capture As Review Candidates

## Status

Accepted for v2 draft.

## Context

The v2 roadmap requires imports from ChatGPT exports, Claude files, Cursor
rules, Markdown, text, and conversation files. The repository already supports
configured provider folder imports, but not explicit one-off capture or
ChatGPT export extraction.

The safety model forbids automatic durable writes and requires secret scanning
before generated candidates enter the review inbox.

## Decision

Add explicit capture to `scripts/provider_import.py` and the unified CLI:

```bash
ai-dememory capture <kind> --path <file-or-directory>
ai-dememory capture <kind> --stdin --title "..."
ai-dememory capture <kind> --text "..." --title "..."
```

Capture kinds are:

- `chatgpt`
- `claude`
- `codex`
- `cursor`
- `windsurf`
- `markdown`
- `text`
- `conversation`

All output goes to `inbox/imports/<kind>/` and remains `status: proposed`.
Rendered candidates are secret-scanned before writing.

Expose MCP `memory.capture_import` for text and repository-local file capture.
The MCP tool rejects absolute paths and paths outside the vault; external paths
remain a CLI-only action.

## Benefits

- Ad hoc lessons and exported chats enter the same review workflow as provider
  imports.
- ChatGPT exports become useful without adding a separate dependency.
- MCP clients can capture non-secret text without filesystem-wide read access.
- Durable memory remains human-reviewed and auditable.

## Limitations

- ChatGPT export parsing is intentionally lightweight and reads only the first
  2 MiB of a JSON export in this milestone.
- Generic JSON, JSONL, Markdown, text, and log captures are excerpt-based and
  may need manual cleanup before promotion.
- Binary files are ignored by path capture.

## Future Risks

- Provider export schemas may change and require parser updates.
- Large exports may need streaming parsers and better deduplication.
- More capture sources may require provider-specific privacy filters before
  rendering candidates.
