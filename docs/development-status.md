# Development status

Updated: 2026-09-14. This is the current handoff, not an accumulated backlog.
Earlier implementation/install receipts remain in Git history.

## Checkout and release reality

- Active worktree: `working/worktrees/product-reset-v3` under the historical
  checkout; branch `codex/v3-learning-workbench`.
- Public `main` read back through GitHub at
  `e7f823ecf223d544b1f2f4cd909fbc42afb3aea3` (PR #57).
- This line builds on V3 baseline `a04a0cd`; previous local increment `d667f96`.
  The large dirty historical V2 checkout and pre-existing `build/` are preserved.
- Source and isolated installed runtime: `3.0.0a1`, unpublished. No version,
  release tag, package publication or merge in this cycle.
- PR #58 remains the original V3 baseline, not a current workbench readiness
  receipt. No new hosted CI is claimed for these local changes.
- [Roadmap](roadmap.md) is the only active product plan. V2 DAGs/TODOs are
  historical input; there is no V2 migration or compatibility backlog.

## Delivered local product

- Small Python core: canonical Markdown, generated Unicode FTS, one selected
  vault, seven top-level commands and lazy optional modules.
- Scoped learn/recall/correct/forget; explicit user statements can be active,
  inference remains provisional, keyed corrections and undo preserve history.
- Scope-bound stdio MCP, project-local Codex/Claude installers and optional
  fail-open UserPromptSubmit recall. No default daemon or model call.
- Local web UI for memory/scopes, providers, ordered fallback, budgets,
  consolidation, source conversations and independent module switches.
- Provider presets, live model discovery, session/environment API keys, an
  optional isolated Codex managed-login adapter and trusted provider plugins.
- Readable conversation titles/workspaces, internal-session filtering, inline
  previews and ten-conversation batches bound to exact scope/routes/text.
- Opt-in per-harness recent-window schedules reuse existing budgets/receipts.
  Pausing/disabling prevents future runs; no OS task or extra watcher.

## This cycle: Codex history that resumes

- Optional **Codex history** mode reads native human JSONL events from the
  beginning; default recent-window behavior remains unchanged.
- Forward windows stop before the next eligible message exceeds 20 messages /
  24,000 characters. The record-read window is at most 2 MB; bounded directory
  discovery and title/provenance reads are separate I/O.
- Persistent per-file byte cursors use the existing durable `runtime.sqlite`,
  not the disposable index. No raw conversation copy is stored in cursor rows.
- A pending range is committed before extraction so appends cannot enlarge an
  interrupted retry. Completed extraction receipts prevent another provider
  call after a crash before cursor advancement.
- Native mirrors/internal scaffolding are excluded; incomplete final lines wait
  for completion. Assistant-only windows advance without a model call.
- Folder pagination reaches beyond the browser's 100-item display and durable
  cursors do not evict after 128 files. Round-robin windows prevent a long/busy
  first conversation from starving the rest.
- UI shows inspected messages/windows, tracked conversations, discovery passes,
  current-file bytes remaining and discard/limit warnings. Unsupported harnesses
  cannot select history mode. Removing a rule removes cursors, not memories.

## Reproducible evidence

- Baseline: 177 tests; 173 passed / four Windows symlink skips.
- Current full suite: 188 tests; 184 passed / the same four skips. Compilation,
  JavaScript syntax and `git diff --check` pass.
- Focused source/HTTP tests: 49 tests; 48 passed / one Windows symlink skip.
  Cases include 131 conversations, 45-message chronological coverage, independent
  identical occurrences, append during failed retry, partial lines, bounds,
  source replacement/truncation, module opt-in, scope and confirmation gates.
- Fresh read-only review found starvation of later conversations and an
  inaccurate I/O claim. Both fixed and re-reviewed; no remaining local-commit
  blocker. This is not a full-branch hosted release review.
- Browser QA at `127.0.0.1:18765`, 1440x1080 and 390x844: create paused rule,
  process 25 synthetic messages in two windows into `project:history-qa`, inspect
  progress and reload persistence. No horizontal overflow, application console
  errors, blank page or error overlay. Browser plugin unavailable; Playwright
  connector used. Screenshots retained outside the repository.
- Wheel: 97,305 bytes, SHA-256
  `a6bbb155352f51448737fb5268a44e1119cabfc838cc49093cdde5fbcb4bce98`.
  Reinstalled in the existing isolated V3 runtime. Installed reader, UI assets
  and CLI help verified from outside both source checkouts.
- No personal-history extraction or automatic schedule enabled by this cycle.
  The previous installed workbench was not listening on port 8765; package
  installation did not start it or change its settings.

## Native Codex acceptance — now verified

- Current native CLI: `0.154.0-alpha.6.2`. A synthetic `gpt-5.6-luna` / `low`
  subscription probe returned successfully with exit 0.
- The old “requires a newer version” blocker is no longer current. An initial
  restricted-shell attempt hit `UnknownIssuer` and was stopped. The normal host
  context succeeded without disabling TLS or reading/changing credentials;
  API-key environment variables were excluded from the successful probes.
- Three independent ephemeral native sessions used the installed-package MCP
  against one disposable synthetic vault in `project:native-qa`:
  1. Context lookup and learn: fictional release day Tuesday.
  2. Context recalled Tuesday; explicit keyed correction stored Friday.
  3. Context recalled Friday; forget undid the correction; context restored Tuesday.
- All seven MCP calls completed without error; all three CLI processes exited 0.
  Models used no shell or direct file tools. Canonical readback showed Tuesday
  active and the Friday correction forgotten; recall did not create extra memories.
- This verifies installed stdio MCP with native Codex, not automatic native hook
  injection or the separate DeMemory-managed subscription provider. Hook trust
  was not bypassed and global client configuration was not edited.
- Native invocation used official
  [CLI execution](https://learn.chatgpt.com/docs/developer-commands?surface=cli)
  and [MCP configuration](https://learn.chatgpt.com/docs/extend/mcp?surface=cli).
  Existing host subscription authentication stayed separate from the temporary
  memory/config directories.

## Next development cycle

1. Complete native trusted-hook acceptance; keep direct MCP, fixture-only hooks
   and optional DeMemory-managed login/generation evidence distinct.
2. Deliver Hermes/Claude cross-harness recall using one extraction owner per
   origin, then active Hermes WAL and DSH compressed input driven by examples.
3. Extend scoped consolidation/procedural memory with one working second-case
   skill export. Current model summaries are global review proposals only.
4. Complete real selected-provider/fallback acceptance with visible budgets.
5. Remote service/admin remains later: identity scopes, TLS/key management and
   two-host restart/restore acceptance before any non-loopback exposure.

## Known limits and rollback

History expects append-only native Codex JSONL; response-only exports need manual
preview. Discovery is limited to 5,000 entries and depth four; 256 MB source-file
limit still applies. Common replacement/truncation is skipped with a warning,
not an automatic rewrite migration. Source cursors do not make canonical
Markdown and admission receipts transactional. Run one workbench writer per
vault; synchronous jobs can block UI requests while a provider runs.

Consolidation inspects at most 100 active memories; scheduled consolidation uses
global scope. Budget prices are estimates, not provider invoice enforcement.
Trusted MCP evidence labels are not independent truth verification. No remote
listener, new runtime dependency, daemon or automatic publication was added.

Rollback: pause/delete the new history rule or disable sources; canonical
memories and receipts remain. For code rollback, revert the scoped feature
commit and reinstall the previous local wheel. Back up durable operational
state with the vault; never remove it as part of an index rebuild.

Before PR readiness, refresh exact base/head and hosted CI and obtain a fresh
exact-diff review. Merge, tag and publication remain separate approval gates.
