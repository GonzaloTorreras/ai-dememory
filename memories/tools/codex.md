---
id: mem_tool_codex_20260614
title: Demo Codex Setup Notes
type: tool
status: active
scope: tool
project: null
tags: [codex, windows, wsl, hooks, mcp, github]
aliases: [codex setup, ai dememory setup]
created_at: 2026-06-14
updated_at: 2026-07-27
confidence: 0.9
sensitivity: public
source:
  kind: codex
  ref: public-canonicalization-review
pin: false
decay: slow
review_after: 2026-09-26
---

# Demo Codex Setup Notes

Current target stack:

- Native Windows tools are preferred for this checkout; use WSL2 when the
  project already lives there or the required runtime is unsuitable on Windows.
- The public repository, installed `ai-dememory` executable, and private vault
  are separate resources. Never use the source tree as the live private vault.
- Codex CLI can run the installed `ai-dememory` commands against an explicitly
  bound vault.
- Context7 and Playwright MCPs may be enabled for docs and browser validation.
- Use the root agent for routine work and at most one fresh bounded read-only
  reviewer for a final PR/security pass. Do not recycle completed agents when
  the host may allocate a new tool stack per turn.
- Native GitHub connector is preferred over gh.
- Hooks and rules should avoid BOM encoded files.
- Generated MCP configs need a nonzero idle lease unless an external supervisor
  owns the process. Package children use Windows Job Objects or POSIX process
  groups; host-owned Codex/browser/plugin processes remain outside package
  cleanup authority.
