---
id: mem_active_context_20260614
title: Demo Active Working Context
type: active
status: active
scope: project
project: ai-dememory
tags: [active, memory, implementation]
aliases: [current context]
created_at: 2026-06-14
updated_at: 2026-08-23
confidence: 0.9
sensitivity: public
source:
  kind: codex
  ref: public-canonicalization-review
pin: false
decay: fast
review_after: 2026-08-26
---

# Demo Active Working Context

The public repository is the canonical development and package-distribution
source. Stable `v2.1.1` peels to
`3dd65a18c5f26c5d03f24c5f3bb719769b581fa6`, is published on PyPI, and was
verified through the protected release workflow `32662792807` plus public
index readback. `v2.1.1rc2`, resolving to
`ea7e1667c874a3cf2a8e1d87b916fb00172b71ce`, is immutable TestPyPI evaluation
evidence with a matching GitHub prerelease and exact-index installation;
`2.1.1rc1` is also historical evidence. Neither is an active recommended
installation route. First-run setup is `pipx install ai-dememory` followed by
`ai-dememory init ~/code/my-memory --wizard`; `--require-version` is a
legacy-compatible diagnostic, not a setup requirement. Continue strengthening
Markdown-canonical storage, SQLite FTS retrieval, MCP interfaces, local review
workflows, and generated maintenance artifacts on clean branches based on
public `origin/main`.

The historical private checkout is research input only: port decisions
semantically, renumber conflicting ADRs, and regenerate every test and release
claim in the public repository. This checked-in memory is public demo data;
real user memory belongs in a separately bound private vault.

The 2.1.1 source line preserves the bounded-autonomy hardening: package-owned
children use explicit process ownership and idle leases; public/private MCP
surfaces are separated; scans, graph responses, protocol queues and generated
history have hard ceilings; scheduler receipts bind exact root/command/plan
state; and release tags require an explicit tag/SHA-bound dispatch. Next work is
evidence and modularization, not a Node rewrite or broader default capability.
