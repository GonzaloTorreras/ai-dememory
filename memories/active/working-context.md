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
updated_at: 2026-08-22
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
source. PyPI exposes published stable 2.1.0. `2.1.1rc1` is an annotated
TestPyPI prerelease with a matching GitHub prerelease and exact-index
installation evidence; it is an evaluation route, not a stable PyPI release.
The current source tree declares the separate untagged and unpublished
2.1.1rc2 candidate, which must not be described as an installable package or
as the immutable rc1 artifact. Continue strengthening Markdown-canonical
storage, SQLite FTS retrieval, MCP interfaces, local review workflows, and
generated maintenance artifacts on clean branches based on public `origin/main`.

The historical private checkout is research input only: port decisions
semantically, renumber conflicting ADRs, and regenerate every test and release
claim in the public repository. This checked-in memory is public demo data;
real user memory belongs in a separately bound private vault.

The current 2.1.0 line is a bounded-autonomy hardening release: package-owned
children use explicit process ownership and idle leases; public/private MCP
surfaces are separated; scans, graph responses, protocol queues and generated
history have hard ceilings; scheduler receipts bind exact root/command/plan
state; and release tags require an explicit tag/SHA-bound dispatch. Next work is
evidence and modularization, not a Node rewrite or broader default capability.
