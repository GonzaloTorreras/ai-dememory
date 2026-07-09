# Import And Capture

`ai-dememory` imports external chats and ad hoc notes as review candidates.
Imports never write durable memory directly. Every generated file lands under:

```text
inbox/imports/<kind>/
```

Review and rewrite candidates before promoting any durable, project, or tool
memory.

## Configured Provider Imports

Detect known local provider folders:

```bash
ai-dememory providers detect
ai-dememory providers plan --json
```

MCP clients can inspect configured import readiness with
`memory.providers_status` and review provider setup commands with
`memory.providers_plan`. These tools report configured, enabled, import-ready,
and recommended command state without reading chat files or writing import
candidates.

Configure a provider path:

```bash
ai-dememory providers configure codex --path ~/.codex --dry-run --json
ai-dememory providers configure codex --path ~/.codex
ai-dememory providers configure claude --path ~/.claude --dry-run --json
ai-dememory providers configure claude --path ~/.claude
```

The configure dry-run validates the provider name, normalizes the chosen path,
reports whether it exists, and shows the `.ai-dememory.toml` section that would
be written. It does not write config, read chat files, or create import
candidates.

Preview configured provider files before writing inbox candidates:

```bash
ai-dememory import-chats codex --dry-run --json
```

Dry-run reads and scans provider files, returns `would_write`, and does not
create or write `inbox/imports/` files.

Import configured provider files after reviewing the preview:

```bash
ai-dememory import-chats codex
ai-dememory import-chats claude --limit 10
```

Provider imports are idempotent for unchanged source files. Each candidate gets
a stable fingerprint from the source path and text; repeat imports skip matching
existing candidates with reason `already imported`.

Supported configured providers are:

- `chatgpt`
- `claude`
- `codex`
- `cursor`
- `windsurf`

## Explicit Capture

Capture a Markdown or text file:

```bash
ai-dememory capture markdown --path ./notes/session.md
ai-dememory capture text --path ./notes/todo.txt
ai-dememory capture conversation --path ./exports/session.jsonl
```

Capture text from stdin:

```bash
printf "Remember this non-secret lesson." | ai-dememory capture text --stdin --title "Session lesson"
```

PowerShell:

```powershell
'Remember this non-secret lesson.' | ai-dememory capture text --stdin --title "Session lesson"
```

Supported capture kinds are:

- `chatgpt`
- `claude`
- `codex`
- `cursor`
- `windsurf`
- `markdown`
- `text`
- `conversation`

## ChatGPT Exports

For ChatGPT `conversations.json` exports:

```bash
ai-dememory capture chatgpt --path ~/Downloads/conversations.json --limit 10
```

The importer extracts conversation titles and user/assistant message parts into
review candidates. It reads at most the first 2 MiB of an export file for this
v2 milestone. Larger exports should be split before import.

## Safety

Imports are scanned after rendering the candidate Markdown. Secret-like content
is skipped and no candidate is written for that item.

The MCP tool `memory.capture_import` supports text capture and
repository-relative file capture. It rejects absolute paths and paths outside
the vault. Use the CLI for explicit external file paths.

The MCP tool `memory.import_chats` accepts `dry_run=true` for the same provider
preview. It still reads provider files, but returns `would_write` instead of
writing import candidates.

Generated candidates are intentionally noisy. Promote only stable,
non-secret facts after review.
