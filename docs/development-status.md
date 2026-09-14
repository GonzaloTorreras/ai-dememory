# Development status

Updated: 2026-09-14. This is the current handoff, not an accumulated backlog.
Earlier implementation/install receipts remain in Git history.

## Checkout and release reality

- Active worktree: `working/worktrees/product-reset-v3` under the historical
  checkout; branch `codex/v3-learning-workbench`.
- Public `main` read back through GitHub at
  `e7f823ecf223d544b1f2f4cd909fbc42afb3aea3` (PR #57).
- This line builds on V3 baseline `a04a0cd`; latest runtime increment `6ce1e0a`.
  The large dirty historical V2 checkout and pre-existing `build/` are preserved.
- Source and isolated installed runtime: `3.0.0a1`, unpublished. No version,
  release tag, package publication or merge in this cycle.
- PR #58 remains the original V3 baseline, not a current workbench readiness
  receipt. No new hosted CI is claimed for these local changes.
- GitHub search found no PR for `codex/v3-learning-workbench` on 2026-09-14.
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

## Retained ingestion increments

- `47eee14`: opt-in Codex chronological history, 20-message / 24,000-character /
  2 MB windows, durable pending ranges and cursors, paginated round-robin folder
  discovery and visible progress. Retries cannot expand with appended messages;
  completed receipts avoid repeated model calls. Internal/mirrored events are
  excluded and incomplete final records wait for completion.
- `e4388a1`: live local Hermes WAL source reading with coherent read-only
  transactions, bounded titles/workspaces/dates, hidden/child filtering and
  visible unreadable-source warnings. WAL-only user commits trigger schedules;
  assistant-only activity does not. No full-copy/checkpoint/repair is performed.

## Retained increment: native Hermes memory-provider adapter

- Disabled-by-default `hermes-memory` module registers the official packaged
  `dememory` provider entry point. Ordinary DeMemory discovery/enablement does
  not import Hermes; Hermes discovery only loads a cheap read-only wrapper.
- Three native tools reuse `CoreServices`: context, learn and forget. Vault and
  scope are fixed by a profile-local binding; session/turn come from lifecycle,
  not model arguments. Recall adds no model call or adapter-owned worker/process.
- Only a literal current-human excerpt can authorize active learning; different
  claims are provisional. The native skill normalizer excludes skill bodies.
  Bot/non-primary/cron/subagent/flush contexts cannot write. Session switches
  clear the prior turn's transient evidence. A lifecycle-binding nonce avoids
  collisions when Hermes reuses a turn number after resume/rewind; this is not
  a durable replay ledger or exact occurrence idempotency across restarts.
- Native sync/mirror/compression/session-end writers remain inherited no-ops.
  No transcript import, source schedule or additional extraction owner is enabled.
- The installer prepares only a new empty Hermes home. Its two official flags
  disable built-in MEMORY.md/USER.md while retaining the external provider.
  Existing profiles, authentication and client settings are untouched. Hermes
  history still exists; this does not replace its conversation storage.
- [Integration documentation](integrations.md#native-hermes-provider-local-alpha)
  covers environment, Hermes profile configuration, module control and rollback.

## Reproducible evidence

- Baseline: 177 tests; 173 passed / four Windows symlink skips.
- Previous cycle: 196 tests; 191 passed / five Windows symlink skips.
- Current full suite: 210 tests; 205 passed / the same five skips. Compilation
  and `git diff --check` pass; no UI asset code changed.
- Focused provider tests: 14/14 pass, including an adapter → MCP correction →
  adapter undo episode, independent scopes, forged provenance, real-quote/unrelated
  claim downgrade, cron and skill exclusion, disablement, discovery, configuration
  preservation, inherited writer no-ops and reused turn ordinals after resume.
- Fresh independent review identified three admission defects (claim authority,
  skill scaffolding and cron provenance). All fixed and re-reviewed; reviewer
  independently reran the provider tests. No local-commit blocker remains. This is not a
  full-branch hosted release/security certification.
- Wheel: 103,324 bytes, SHA-256
  `4ddb81a0879eded1cc18f4170fd33a9c18748387a0852525410b495af736169a`.
  Reinstalled in the existing isolated V3 runtime. Outside both checkouts, its
  actual packaged entry point instantiated the official Hermes ABC at commit
  `1ad89ac018f26a4f21817ebf37bb09f508656d63`. The upstream pure skill normalizer,
  scoped learning and inherited writer no-ops passed a synthetic contract smoke.
  The installed CLI also prepared a disposable empty home with the correct binding.
- Browser QA of the installed package at `127.0.0.1:18767`, 1440x1080 / 390x844:
  enable Hermes, reload persisted state, disable it, preserve the other harness
  switches. No blank page, overlay, overflow or console warnings/errors. Browser
  plugin was not exposed to that QA turn; Playwright connector used. The later
  installation check below verified the built-in Browser. Screenshots stay outside Git.
- No real Hermes/Claude process, new model call, personal-profile extraction,
  credential copy or installed personal automation was started. Full Hermes
  loader/manager/authenticated-model acceptance remains **unverified**; contract
  and synthetic cross-adapter tests are not a native-client episode.

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

## Latest local installation: Codex (2026-09-14)

- At the user's explicit request, installed the existing V3 Codex integration
  in the historical checkout and active V3 worktree. Both use one new, empty
  private V3 vault and `project:ai-dememory`; the test vault, V2 memories and
  global Codex settings remain unchanged. The separate local selector enables
  only `harness-codex`, `mcp` and `workbench`.
- Generated client files contain machine-local paths and are excluded through
  shared Git `info/exclude`, not committed. The native CLI reads both scoped MCP
  configurations successfully in the normal host context.
- All 23 focused harness/MCP tests passed. Direct invocation of each installed
  hook returned valid scoped context (891 / 328 ms including process startup);
  both installed MCP processes initialized and exposed seven tools (265 / 234
  ms). These single-run timings are smoke observations, not latency benchmarks.
  No model calls or transcript reads; zero memories created; all smoke processes
  exited. A fresh independent read-only review found no installation blocker.
- **Activation gate remains:** review/trust the exact hook through Codex `/hooks`
  and demonstrate injection from a native prompt in a fresh session. No trust
  bypass or trust-store edits were used. Check that each task shows exactly one
  DeMemory UserPromptSubmit handler; matching hook sources accumulate.
- Browser is included in the current desktop app, not a missing separately
  installed dependency. Opened its official documentation in the built-in browser
  and inspected the rendered page successfully. No extra browser package was added.

## Next development cycle

1. Next safe local slice: scoped consolidation/procedural memory with one working
   second-case skill export. Current model summaries are global review proposals.
2. Complete native Hermes/Claude episodes and trusted Codex-hook acceptance in
   isolated client environments; do not substitute contract/fixture evidence for
   client execution or bypass authentication/trust. Keep optional DeMemory-managed
   login/generation evidence separate from the already verified Codex MCP route.
3. DSH compressed input and Hermes lineage remain example-driven reader gaps.
4. Complete real selected-provider/fallback acceptance with visible budgets.
5. Remote service/admin remains later: identity scopes, TLS/key management and
   two-host restart/restore acceptance before any non-loopback exposure.

## Known limits and rollback

The native Hermes adapter is local-only, one fixed vault/scope per profile, and
does not ingest transcript/mirror callbacks. It retains only a bounded current
user instruction in process memory until the next turn/session/shutdown. Model
claims do not independently prove truth, even with literal quote matching.
Disable `hermes-memory` to stop its calls; restore Hermes built-in flags separately
if desired. Profile rebinding requires a client restart. No vault backup is
automatically added to Hermes backups; preserve DeMemory state separately.

Hermes live reading is same-host/local-disk only and limited to root-session
recent windows, not exhaustive history. Database plus sidecars must fit 256 MB;
the 250 ms SQL deadline is per transaction, not per folder. UNC paths are rejected,
but mapped/POSIX network mounts are not detected. Filesystem prechecks do not
claim an adversarial path-swap sandbox. Busy/unsafe databases are skipped visibly.
The implementation follows official [SQLite WAL](https://www.sqlite.org/wal.html)
and [read-only URI semantics](https://www.sqlite.org/uri.html), with optional
session fields from the [Hermes schema](https://github.com/NousResearch/hermes-agent/blob/main/hermes_state_common.py).

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

Rollback: pause/delete affected source rules or disable sources; canonical
memories and receipts remain. For code rollback, revert the scoped feature
commit and reinstall the previous local wheel. Back up durable operational
state with the vault; never remove it as part of an index rebuild.

Before PR readiness, refresh exact base/head and hosted CI and obtain a fresh
exact-diff review. Merge, tag and publication remain separate approval gates.
