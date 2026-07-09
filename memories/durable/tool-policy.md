---
id: mem_tool_policy_20260614
title: Tool Policy
type: durable
reviewed: true
reviewed_by: Example Maintainer
reviewed_at: 2026-06-14
status: active
scope: tool
project: null
tags: [codex, github, tools, policy]
aliases: [tool rules, github connector policy]
created_at: 2026-06-14
updated_at: 2026-06-14
confidence: 0.9
sensitivity: public
source:
  kind: codex
  ref: setup-history
pin: true
decay: none
review_after: 2026-09-14
---

# Tool Policy

- For GitHub work in Codex, prefer native GitHub connector tools.
- If GitHub tools are not visible, run tool discovery before using gh.
- Use `gh` only when connector capabilities are insufficient or local shell
  behavior is explicitly required.
- For library docs, prefer Context7 when available.
- For browser validation, prefer Playwright MCP when available.
