---
id: mem_architecture_20260614
title: Memory System Architecture
type: durable
status: active
scope: personal
project: ai-dememory
tags: [memory, architecture, codex, obsidian, sqlite, mcp]
aliases: [personal memory repo, multi llm memory]
created_at: 2026-06-14
updated_at: 2026-06-14
confidence: 0.95
sensitivity: internal
source:
  kind: codex
  ref: planning-thread
pin: true
decay: none
review_after: 2026-09-14
---

# Memory System Architecture

## Verdict

Use hybrid Markdown plus SQLite FTS.

- Markdown/Obsidian is canonical and human editable.
- GitHub private repo provides sync and versioning.
- SQLite FTS is generated retrieval infrastructure.
- MCP is the common interface for Codex, Claude, and Gemini.
- Vector search is a future optional layer, not the foundation.

## Acceptance Criteria

1. Markdown can be edited in Obsidian.
2. SQLite can be rebuilt from Markdown.
3. LLMs retrieve memory through MCP with source, confidence, status, and path.
4. Durable memories are not automatically overwritten.
5. Secret scanning blocks sensitive content.
6. Vector search can be added without changing canonical memory.
