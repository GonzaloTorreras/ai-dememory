---
id: mem_tool_codex_20260614
title: Demo Codex Setup Notes
type: tool
status: active
scope: tool
project: null
tags: [codex, wsl, hooks, mcp, github]
aliases: [codex setup, ai dememory setup]
created_at: 2026-06-14
updated_at: 2026-06-14
confidence: 0.85
sensitivity: public
source:
  kind: codex
  ref: setup-history
pin: false
decay: slow
review_after: 2026-08-14
---

# Demo Codex Setup Notes

Current target stack:

- WSL2 or Linux-like execution is preferred for development when available.
- Codex CLI can run the local `ai-dememory` commands.
- Context7 and Playwright MCPs may be enabled for docs and browser validation.
- Review agents may be used for PR, security, QA, docs, and final-review tasks.
- Native GitHub connector is preferred over gh.
- Hooks and rules should avoid BOM encoded files.
