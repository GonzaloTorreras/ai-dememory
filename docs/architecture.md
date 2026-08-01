---
id: mem_architecture_20260614
title: ai DeMemory Architecture
type: durable
status: active
scope: project
project: ai-dememory
tags: [memory, architecture, codex, obsidian, sqlite, mcp]
aliases: [memory tool architecture, multi llm memory]
created_at: 2026-06-14
updated_at: 2026-07-27
confidence: 0.95
sensitivity: public
source:
  kind: codex
  ref: public-canonicalization-review
pin: true
decay: none
review_after: 2026-10-26
---

# ai DeMemory Architecture

## Verdict

Use hybrid Markdown plus SQLite FTS.

- Markdown/Obsidian is canonical and human editable.
- The public `ai-dememory` repository distributes the tool and public demo
  fixtures; it is never a personal vault.
- A separate private vault, optionally synchronized through its own private
  repository, stores real user memory.
- SQLite FTS is generated retrieval infrastructure.
- MCP is the common interface for Codex, Claude, and Gemini.
- A versioned resource-policy layer resolves `minimal`, `balanced`, or `active`
  ceilings before recall, imports, hooks, maintenance, or scheduling run.
- MCP profiles are enforced by the Python server; client allowlists are defense
  in depth rather than the capability boundary. Public repository use has a
  server-forced three-tool public ceiling; generated private-vault clients
  default to four-tool core.
- MCP stdio self-expires when idle, and package-owned external work runs behind
  one bounded process-tree supervisor with non-interactive stdin: Windows Job
  Objects and POSIX owned sessions/process groups.
- Canonical/secret discovery, files/bytes, graph pages/nodes/edges, MCP
  frames/queues/output, and disposable SQLite audit history are all bounded.
- The onboarding wizard and scheduler use exact preview fingerprints and
  vault-bound, exact-definition receipts. Installation remains passive.
- Vector search is a future optional layer, not the foundation.
- Python owns domain policy and durable writes. A future TypeScript/React visual
  plane may use generated contracts but cannot become canonical authority.

## Acceptance Criteria

1. Markdown can be edited in Obsidian.
2. SQLite can be rebuilt from Markdown.
3. LLMs retrieve memory through MCP with source, confidence, status, and path.
4. Durable memories are not automatically overwritten.
5. Secret scanning blocks sensitive content.
6. Vector search can be added without changing canonical memory.
7. Resource overrides cannot escape hard min/max ceilings.
8. ai-dememory runtime model/embedding calls remain zero unless a future,
   separately reviewed architecture decision changes that contract.
