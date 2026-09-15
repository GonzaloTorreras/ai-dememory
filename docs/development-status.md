# Development status

Updated: 2026-09-15. This is the current handoff, not an accumulated backlog.
Earlier implementation/install receipts remain in Git history.

## Checkout and release reality

- Active worktree: `working/worktrees/product-reset-v3` under the historical
  checkout; branch `codex/v3-learning-workbench`.
- Public `main` read back through GitHub at
  `e7f823ecf223d544b1f2f4cd909fbc42afb3aea3` (PR #57).
- This line builds on V3 baseline `a04a0cd`; this increment starts at `6d9e717`.
  The large dirty historical V2 checkout and pre-existing `build/` are preserved.
- Source remains `3.0.0a1`, unpublished. The user's isolated V3 runtime now
  includes the global Codex integration recorded below. The default selector and
  global client connection were configured; existing account state and unrelated
  settings were preserved. No version, release tag, package publication or merge.
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
- Scope-bound stdio MCP, user-wide project-aware Codex installation, explicit
  project-local Codex/Claude connections and fail-open UserPromptSubmit recall.
  No default daemon or model call.
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

## Previous integration evidence

- Baseline: 177 tests; 173 passed / four Windows symlink skips.
- Previous cycle: 196 tests; 191 passed / five Windows symlink skips.
- That integration's full suite: 210 tests; 205 passed / the same five skips. Compilation
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

## Prior local installation: Codex (2026-09-14)

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
- The user activated the hook on 2026-09-15. A subsequent native prompt in the
  current project task supplied DeMemory context and a previously verified
  project lesson. This observes current-task injection, not fresh-project,
  simultaneous-project or global acceptance. No trust bypass or trust-store
  edits were used. Check exactly one handler per task; matching sources accumulate.
- Browser is included in the current desktop app, not a missing separately
  installed dependency. Opened its official documentation in the built-in browser
  and inspected the rendered page successfully. No extra browser package was added.

## Previous cycle: scoped consolidation scheduling (`9d38e01`)

- One saved `schedule.scope`, editable in the existing workbench with scope
  suggestions, independent of browsing/manual-run scope. Empty scopes remain
  selectable. A missing optional scope means global; no V2 reader/migration.
- A persisted schedule cadence anchor is separate from last-run metadata.
  Manual success/failure in another scope cannot delay the scheduled run or
  distort later interval edits. Scope changes/re-enablement start a fresh interval.
- Last-run scope and manual target are explicit in UI and API results. Project
  cleanup still makes zero model calls and cannot create global proposals;
  inactive originals remain in Markdown history. No extra scheduler/module.
- Focused checks: 55 passed. Full suite: 216 tests, 211 passed / five expected
  Windows symlink skips. Compilation, JavaScript syntax and diff checks pass.
  Fresh exact-diff read-only review found no blocker and independently passed
  all 43 jobs/workbench tests.
- Built-in Browser QA at `127.0.0.1:18768`, 1440x1080 / 390x844: save a daily
  alpha-scope schedule, manually clean beta, verify alpha's due time unchanged,
  reload and confirm persistence. No blank page, overlay, mobile overflow or
  relevant console errors. The initial UI save was rejected as a real schedule;
  after read-only proof of the disposable fixture, the same action was approved.
- Wheel: 103,723 bytes, SHA-256
  `649b4b0743d535eb580b9ce257e5452352bfcbc3ad72b756ff8e651d3a123c41`.
  Disposable install outside the checkout passed actual packaged CLI
  setup/save/recall/status, schedule/restart behavior and UI-asset checks.
  No personal vault, hook trust, global client config or model call was involved.

## Previous cycle: Codex provider executable discovery (`dc019d6`)

- User report: `codex_binary_required` while starting managed login. This code
  is emitted before authentication when the discovered/explicit path is not an
  accepted executable. The historical dashboard environment was not captured;
  current host and persistent PATH checks already resolve a native executable.
  Do not claim wrapper shadowing as the verified cause of that original attempt.
- Windows now prefers `codex.exe` before generic `codex`. Explicit overrides
  remain strict, with no shell-wrapper execution, filesystem crawling or new
  dependency. Missing/invalid executables have static actionable guidance in
  both login and status; failed attempts clear stale sign-in links and codes.
- Forty focused tests passed, also independently rerun by the read-only reviewer.
  Full suite: 222 tests, 217 passed / five Windows symlink skips. Compilation,
  JavaScript syntax and diff checks passed. No exact-diff review blocker remains.
- Built-in Browser QA: disposable account fixture at `127.0.0.1:18769`, desktop
  1280-wide and mobile 390x844. Pending flow, failed status, failed retry, guidance
  and link/code cleanup verified. No blank page, overlay, horizontal overflow or
  console warning/error. QA found the shared request helper discarded error
  guidance; it was fixed and the flow rechecked. No real sign-in page was opened.
- Source and installed package each initialized the native Codex AppServer,
  read an unauthenticated disposable account and reaped the child/reader/scratch.
  No login, token copy, model call, personal extraction or hook-trust change.
- Wheel: 104,032 bytes, SHA-256
  `aadce9e86bf91ab50f4a0b17d14b43d3584a459b8f2741c66cc93d94b85f54bd`.
  Disposable package CLI/settings smoke passed before updating the existing
  isolated runtime with this exact wheel. Packaged UI and native startup readback
  passed afterwards. The runtime has no pip; the existing bundled pip targeted
  it explicitly, without adding pip/dependencies or changing the global PATH.
- User action: restart the workbench and retry provider sign-in. Authentication
  is still user-completed and must not be inferred from the hook activation or
  the successful unauthenticated account read. The continuation pauses at this
  acceptance boundary instead of repeating sign-in attempts. This optional
  provider check does not block local CLI/MCP integration development.

## Previous cycle: V2 runtime retirement and global V3 plan (`6d9e717`)

- The user's separate local acceptance invoked historical V2 scripts after
  launcher/dependency failures and created a review proposal, not a V3 memory.
  It did not prove the installed V3 hook/MCP route. Only a bounded verified
  project lesson was retained in the private V3 vault; no transcript or private
  capture is repository content.
- Read the UV installation receipt and package metadata: the global entry point
  belonged to `ai-dememory 2.1.0`. The exact owned tool directory was checked
  before `uv tool uninstall ai-dememory`; UV removed its one executable.
  Readback confirmed both that directory and launcher absent, and UV reports no
  remaining tools. No manually constructed recursive delete was used.
- The isolated V3 runtime, its selector and both V3/legacy vaults are preserved.
  Outside either checkout, the installed runtime reports `3.0.0a1` and selected
  vault status successfully. At that checkpoint the bare `ai-dememory` command
  was absent from PATH; the global replacement is delivered in this cycle below.
- A bounded host inventory found no matching legacy-script/runtime processes or
  DeMemory Windows scheduled tasks. Three relevant Codex automations were already
  paused and remain unchanged. Inspected global Codex config/hooks have no DeMemory
  entries; the two known project-local integrations still point to V3 with one
  fixed scope. No matching standalone DeMemory skill directory was found.
- The active V3 worktree, the dirty historical parent and pre-existing `build/`
  are untouched by removal. The parent cannot be deleted while it owns this
  worktree's shared Git metadata and unreviewed edits. No V3 runtime update,
  release/publication, trust, authentication or global-client config change in
  this cycle.
- Read-only code exploration confirmed the missing pieces: global installer
  merging/ownership, one selector across entry points, reliable native project
  binding, a common scope resolver and client-disable precedence. The existing
  selected-vault resolver and fixed-scope MCP are reused, not replaced by a new
  framework. The ordered plan lives only in [the roadmap](roadmap.md#now-one-global-v3-installation-isolated-projects).
- Verification: 49 focused core/harness/MCP tests, 46 passed and three expected
  Windows symlink skips; `git diff --check` passed. Independent read-only review
  found no plan blocker after clarifying that only V2 was uninstalled. This is a
  four-file documentation change, not implementation or global-install acceptance;
  the full suite, browser QA and hosted CI were not rerun for this planning diff.

## Next development cycle

1. Global Codex installation is delivered below. Next expose project aliases and
   exclusions in the existing workbench, using the same small local mapping.
2. Verify a native linked-worktree episode and task relocation/reconnect. Native
   new-project and simultaneous-task checks pass; do not generalize them to every
   client lifecycle/version. Keep provider login separate.
3. Resume native Hermes/Claude episodes, evidence-backed advisory skill export,
   measured DSH/Hermes reader gaps and selected-provider/fallback acceptance.
4. Remote service/admin remains later: identity scopes, TLS/key management and
   two-host restart/restore acceptance before any non-loopback exposure.

## This cycle: installed global V3 and native project isolation

- Added automatic local project identity shared by hook, CLI and Codex MCP:
  Git common-directory identity groups worktrees; unrelated same-name folders
  and projectless workspaces stay separate. Explicit aliases/exclusions live
  beside the selector. No transcript read, registry daemon or Git subprocess.
  Home/root context has no implicit global-write fallback. Alias/exclusion UI
  is not implemented yet; current controls reuse the harness command.
- The native CLI and one AppServer with two tasks were probed before binding
  implementation: each starts its own MCP process in the task directory. Native
  calls supply thread/turn metadata. Auto MCP fixes its project scope, latches
  the caller thread and stamps learning identity from that metadata, rather than
  model guesses. Reused-thread/missing-metadata errors preserve the request ID.
  This is a tested local-client contract, not remote authentication.
- Client toggles normalize the generic harness switch without importing the
  sibling. Auto MCP rechecks module/project disablement and rebinding at every
  call; exclusions apply across explicit aliases sharing the same project scope.
  Manual remember/recall now accept `--scope auto` or an explicit scope; their
  existing default is global. Status reports runtime, selector and project.
- User installer merges one owned TOML block and hook, preserves unrelated
  settings, rejects unowned conflicts and retains private ownership receipts.
  Selector enablement participates in the same rollback transaction. Exact
  generated local connections can be retired with their scopes retained;
  uninstall restores only unchanged owned edits, never later user changes.
- Full regression: 237 tests, 232 passed / five expected Windows symlink skips.
  Compilation and diff checks pass. The fresh read-only reviewer reproduced
  and helped close correlated-error, duplicate-hook, shared-exclusion and
  selector-atomicity defects; independently reran 45 focused tests. This is a
  functional/ownership review, not a completed formal security scan or release
  certification. No UI asset changed; rendered browser QA was not repeated.
- Installed wheel: 111,434 bytes, SHA-256
  `ebcf99d3d47173b9ed583c342ddcded3dcfeaf5f459b3aa63c5b3ccafc4d1cde`.
  Built from a disposable copy to preserve pre-existing `build/`. Isolated wheel
  setup/save/recall/status, schedule/restart and packaged-asset smoke passed.
  Subsequent documentation edits do not change its tested runtime code.
- Five native Luna sessions against an installed-wheel disposable vault made
  ten successful MCP calls: learn Tuesday, simultaneous A/B recall with B empty,
  correct to Friday, then undo back to Tuesday. A separate projectless scope
  remained empty. An initial `never` approval policy correctly refused a write;
  the successful run used Codex's normal automatic approval review. Global
  approval policy was not weakened and write tools are not labeled read-only.
- Installed that exact wheel into the existing isolated runtime and exposed its
  packaged entry point on the already configured user PATH. The previously absent
  default Windows config directory is a junction to the existing V3 selector,
  resolved canonically; no managed-login credentials were moved or copied.
  From outside the checkout, the bare command resolves V3 and the selected vault.
- Installed one global native Codex MCP plus UserPromptSubmit hook; retired the
  two exact generated local connections, preserving `project:ai-dememory` in the
  shared mapping. Normal-host Codex readback confirms enabled stdio, no fixed
  cwd and `--auto-scope`. A restricted-shell readback did not see the personal
  Codex config; normal-host verification succeeded without altering permissions.
- The user trusted the new global hook. Two subsequent fresh native projects
  using the actual global config each completed context/status calls and recorded
  one hook receipt. Hook-internal lookup timings were 94/110 ms, not p95 or full
  process-start latency benchmarks. No canonical memories were created in this
  read-only check. All owned native test CLI processes exited.
- Separately, the current task used native MCP learning to save one verified
  installation outcome and retrieved it again in its bound project scope.
  Native provenance was stamped correctly; no raw conversation was stored.
- Post-test host inventory found eight retained MCP connections owned by Codex
  AppServer processes: each had a small Windows venv launcher plus its Python
  worker, about 25 MB combined working set per connection (202 MB summed across
  all eight; shared pages may be counted repeatedly). No probe processes remained.
  A live parent does not prove an active task, and this snapshot neither proves
  nor rules out a client lifecycle leak. Global MCP is per loaded connection,
  not one shared service; retained-connection lifecycle remains a measured gap.
- Private V3/legacy vaults, account state, unrelated settings and the dirty parent
  checkout remain intact. Existing client processes may retain their old MCP
  connection until reconnect/restart; new tasks use the global configuration.
  No daemon, network listener, history scan, version tag, publication or merge.

Local rollback: run `ai-dememory serve harness-codex uninstall --user` before
removing its module, then restart Codex. Reinstall the previous local wheel if
rolling back runtime code. Remove a Windows selector junction only as a link,
never recursively delete its target. Vaults and credentials are not uninstall
targets. The installed readme metadata predates this cycle's documentation-only
clarifications; release packaging must rebuild and refresh exact artifact evidence.

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

Consolidation inspects at most 100 active memories in its exact scope. There is
one saved consolidation schedule per vault, not a per-project scheduler fleet.
Budget prices are estimates, not provider invoice enforcement.
Trusted MCP evidence labels are not independent truth verification. No remote
listener, new runtime dependency, daemon or automatic publication was added.

Rollback: pause/delete affected source rules or disable sources; canonical
memories and receipts remain. For code rollback, revert the scoped feature
commit and reinstall the previous local wheel. Back up durable operational
state with the vault; never remove it as part of an index rebuild.

Before PR readiness, refresh exact base/head and hosted CI and obtain a fresh
exact-diff review. Merge, tag and publication remain separate approval gates.
