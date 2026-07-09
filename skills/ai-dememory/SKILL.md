---
name: ai-dememory
description: Use when Codex needs to work with this repository as a personal multi-LLM memory system: recall existing Markdown memory, validate or index memories, run safe secret checks, export LLM context, write proposal captures, review inbox entries, or operate the local MCP memory server. Also use when making changes to memory schema, scripts, templates, MCP tools/resources/prompts, or automation docs.
---

# ai DeMemory

This repo treats Markdown as canonical memory. SQLite indexes, reports, and
distilled context are generated artifacts.

## Core Rules

- Never store secrets, credentials, tokens, cookies, private keys, service
  account JSON, `.env` contents, or recovery codes.
- Never overwrite `memories/durable/` from an LLM capture. Write proposals to
  `inbox/llm-captures/` and require human review before promotion.
- Run secret scan and schema validation before indexing or exporting context.
- Keep generated files reproducible from Markdown.
- Private/sensitive memory is excluded from default MCP resources, search, and
  exports.

## Common Commands

Run from the repo root:

```bash
python3 scripts/ai_dememory.py validate
python3 scripts/ai_dememory.py secret-scan
python3 scripts/ai_dememory.py index
python3 scripts/ai_dememory.py search <query> --limit 5
python3 scripts/ai_dememory.py export-context
python3 scripts/ai_dememory.py consolidate --dry-run
python3 scripts/ai_dememory.py mcp --stdio
```

Use `py -3` instead of `python3` on Windows when needed.

## Workflow

1. Read `docs/schema.md` before editing memory frontmatter.
2. Add or modify canonical memory under `memories/` only when it is reviewed and
   non-secret.
3. Put uncertain LLM captures under `inbox/llm-captures/`.
4. Run validation and secret scan.
5. Rebuild the index.
6. Use search or MCP resources/prompts for recall.

## MCP Notes

- Server path: `mcp/server/memory_mcp.py`.
- Product target: `docs/mcp-v2.md`.
- Exposed tools include `memory.search`, `memory.get`,
  `memory.write_proposal`, `memory.mark_seen`, `memory.reindex`,
  `memory.consolidate`, and `memory.secret_scan`.
- Exposed resources use `memory://id/{id}` and `memory://path/{path}` for
  public/internal canonical memory.
- Exposed prompts are `memory_recall_context`, `memory_capture_proposal`, and
  `memory_review_inbox`.

When improving MCP behavior, keep tool outputs structured, path access
repository-bounded, and write operations proposal-only unless the user
explicitly approves a durable memory change.
