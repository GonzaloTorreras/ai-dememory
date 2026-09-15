# V3 development plan

This is the single active product plan. Updated 2026-09-16 for first-run Codex
hooks and opt-in Windows consolidation. Usable global installation takes priority
over procedural export, remote networking and further ingestion frameworks.

## Product outcome

One conversation teaches a scoped lesson; another retrieves it accurately;
a correction replaces it; unrelated projects remain isolated. Routine learning
does not require a human approval queue. A local UI controls memory, model
routes, fallback, consolidation and budgets. The same core will later serve
several hosts.

## Keep / change

- Keep Python, canonical Markdown, disposable search indexes, atomic writes,
  one selected vault, lazy modules and a small public CLI.
- Replace universal proposal-only integration with evidence-aware admission,
  provenance, scoped retrieval and reversible corrections. Inferences remain
  provisional; explicit user corrections need no second approval.
- Package installation stays passive. An enabled workbench is an explicit
  foreground process with local web UI and optional scheduled jobs. An explicitly
  installed Windows one-shot task checks consolidation without a resident worker;
  source ingestion continues to require the foreground workbench.
- Keep operational cursors, budget reservations and job receipts outside the
  disposable index. They must survive an index rebuild.
- No V2 migration, new gate DAG, per-function ADRs, adaptive ranking reward,
  default vectors or separate Node runtime.

## Delivery sequence

Current increment: `setup --with-codex --with-schedule --yes` installs the optional
global Codex hooks/MCP and current-user Windows consolidation task. SessionStart
restores brief guidance after resume/compact without a Stop continuation loop.
The OS task shares the existing scope/cadence/budgets and job lock with the UI,
has owned install/status/remove and does not enable history ingestion. See
[automation](automation.md). Native task acceptance and publication receipts are
recorded in development status, not inferred from this plan.

Latest local fix: Codex provider startup prefers the native Windows executable
over shell launchers, retains strict explicit overrides and gives actionable
login/status errors. Native account-read startup is verified with a disposable
empty account; successful managed login and generation remain separate checks.

Previous increment: one saved consolidation scope in the workbench, durable
per-schedule cadence and explicit last-run/manual scopes. An unrelated manual
run cannot postpone the schedule. Project cleanup remains local and deterministic;
procedural memory and tested skill export follow global installation; they are
not shipped behavior.

Earlier increments: readable Codex conversation titles/workspaces, internal
session filtering, accordion previews, multi-selection, shared scope selector,
independent Codex/Claude module switches and per-harness source schedules.
Codex now also has opt-in chronological history windows, persistent retry cursors,
folder pagination and UI progress. This remains bounded discovery, not exhaustive
historical consolidation. Hermes source reading also supports local live WAL,
session titles and bounded read transactions; it is not a native memory provider.
The separate opt-in `hermes-memory` adapter now implements Hermes's native
provider contract, fixed scope and literal-evidence learning using the same core.
Its installed contract smoke passes; full Hermes client acceptance is still next.
Next ingestion work should be driven by measured gaps: DSH compressed input,
Hermes conversation lineage and native cross-harness episodes.

Every row is a complete user-visible slice, not empty interfaces.

| Slice | Outcome | Acceptance |
| --- | --- | --- |
| Local learning workbench (implemented alpha) | Configure providers and ordered fallback, learn a scoped fact, retrieve its relevant passage, inspect activity, set consolidation interval and budgets in UI | Settings survive restart; mocked provider failure selects fallback within budget; invalid input creates no memory; inference stays provisional. Live model acceptance remains pending |
| Correction and hygiene (implemented alpha) | Explicit keyed replacement, exact unkeyed dedupe, undo, inactive-state filtering and durable extraction receipts | Completed extraction retries return original admissions without another provider call; correction wins only in its scope; history remains inspectable. Interrupted two-store writes remain a documented limit |
| Codex integration (earlier project-local alpha evidence) | Scope-bound MCP tools, project-local installer and bounded prompt recall | Three native Luna sessions completed the project-local MCP learning/correction/undo episode. This historical checkpoint is extended by the global acceptance below |
| Global V3 installation (installed local alpha) | One V3 command and selector, native project-bound Codex MCP and one trusted prompt hook, no V2 fallback | Native installed learning/correction/undo and simultaneous project isolation pass; two new projects use the actual global configuration and trusted hooks. Worktree identity has deterministic tests; wider client/version and lifecycle cases remain below |
| Hermes and Claude (Hermes adapter implemented alpha) | Native Hermes provider, Claude hooks/MCP, one extraction owner per origin | Synthetic Hermes-adapter → MCP correction → Hermes undo passes; transcript/mirror callbacks are no-op. Full native Hermes/Claude episodes remain pending |
| Incremental ingestion (Codex history implemented alpha) | Authorized native Codex deltas, occurrence receipts, durable byte cursors, bounded folder pagination and visible progress | Failed windows retain their exact range across append/restart; separate positions remain separate occurrences; no re-extraction on assistant-only activity. Native rotation/rewrite and other harnesses remain incomplete |
| Consolidation and skills (scoped scheduling implemented alpha) | One saved scope/cadence, deterministic project cleanup and visible manual target; procedural knowledge and tested skill export follow global installation | Scope and cadence survive restart; other-scope manual runs do not postpone them; repeated cleanup converges without model calls. Future recipes must work in a second case with tests and rollback |
| Remote service/admin (later) | HTTP MCP/event service on PC/Raspberry, LAN/Internet, admin UI | Identity-based scopes, TLS, revocation, two-host restart/replay and restore tested before exposure |

DSH is [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness).
The optional manual sources module now previews its plain JSONL, Codex/Claude/Pi
exports and Hermes databases (live local WAL or checkpointed snapshots).
Compressed DSH and Hermes lineage remain explicit gaps. The Hermes reader is
bounded recent-window extraction, not exhaustive unattended ingestion.

## Now: one global V3 installation, isolated projects

V2's owned tool installation is removed. The native V3 command now works outside
the checkout through one selected configuration. `serve harness-codex install
--user` installs an owned global MCP block and one prompt hook; exact known
project connections can be retired without changing their scopes. The user's
global installation and trusted hooks passed native read-only checks in two new
projects. See [development status](development-status.md) for the exact receipt.

The original slices below remain the acceptance contract, not five new tasks.
Runtime binding, installer ownership, scope controls and CLI diagnostics are
implemented. Project-settings UI and broader lifecycle/client acceptance are
still follow-up work; do not claim those from the local alpha receipt. Keep the
existing setup, harness, status and UI surfaces, with no additional framework,
daemon or top-level CLI.

1. **One discoverable command and one selector.** Install the exact local V3 wheel
   into one stable per-user runtime and expose its packaged entry point on PATH.
   V3 is unpublished: an unpinned public package install is not this artifact.
   Reuse `config.py`; selected-vault lookup already works outside the checkout.
   Align CLI, workbench, hooks and MCP on the same selector without merging V2
   config. Keep explicit isolated selectors available for tests. Extend existing
   status with runtime/version/selector provenance. From a fresh shell outside
   any repo, prove version, setup, save, recall and status against a disposable
   vault, without `PYTHONPATH`, source-script fallback or ad hoc dependencies.
   Upgrading/reinstalling must preserve configuration and Markdown; removing the
   package must leave both intact.
2. **Prove native project binding before global MCP.** Use two simultaneous native
   Codex tasks to establish which client-provided root/session information is
   actually available to MCP. The current server has only a fixed binding; its
   launch cwd and model-supplied tool arguments are not an authoritative active
   project. Reuse that bound-scope enforcement after resolving reliable host
   context. Do not assume MCP roots support or use one mutable "current project"
   shared by every session. If the client cannot supply a reliable binding, keep
   the working per-project MCP and provide an explicit project connection through
   the existing setup flow. Report the limitation; do not advertise global
   learning merely because a global recall hook works.
3. **One small shared project resolver.** Explicit local folder-to-scope mappings
   take precedence. Git worktrees share their Git common-directory identity by
   default; unrelated clones/folders do not merge by basename or remote URL.
   Derive an opaque ID deterministically from local identity; persist only
   explicit aliases/exclusions, so a rename can be rebound deliberately without
   losing memory. This avoids an automatically written discovery registry. Give projectless task
   workspaces their own identity. An unknown/home context must not silently write
   global memory: ask for a project binding or skip project recall with an
   actionable diagnostic. Use trusted hook cwd, never transcript contents, for
   hook resolution. Make global sharing explicit, preserve project-plus-global
   reads, and reuse the same resolver in each verified client adapter. Add scope
   selection to existing manual remember/recall and show resolution/reason in
   status (implemented); add project editing to UI next. Prove same-name folder
   separation and intentional worktree sharing.
4. **One owned integration per event.** Extend the existing installer with a user
   target and idempotent merge/uninstall of identifiable DeMemory entries. Parse
   and preserve unrelated TOML/JSON, keep local before/after rollback material
   private, and restore only unchanged owned edits; never overwrite later user
   edits. Inspect known installed projects and the current project for owned
   duplicate handlers; do not crawl all disks. Detect conflicts when another
   project is encountered. Codex hooks from global and project sources
   [accumulate rather than replace each other](https://learn.chatgpt.com/docs/hooks),
   so prove exactly one callback with both sources present. Retain normal user
   trust for changed definitions. Client-specific disablement must take precedence
   over the generic harness module; per-project exclusions must stop recall and
   learning consistently, not just hide the UI switch. Global
   [MCP configuration](https://learn.chatgpt.com/docs/extend/mcp) must not weaken
   the binding proven in slice 2. Test malformed config, repeat installation,
   partial failures, rollback and preservation of unrelated clients/settings.
5. **Installed native acceptance, then wider harness coverage.** In fresh project
   A, learn a synthetic fact; fresh A recalls, corrects and undoes it. Project B
   cannot read or mutate A; A's worktree shares intentionally; a projectless task
   stays separate. Repeat with simultaneous tasks, a runtime upgrade and client
   restart. Check the actual hook callback and MCP result, disabled-project
   behavior, bounded latency and owned-child exit. Provider login is optional,
   not a prerequisite for zero-extra-model local recall or host-assisted learning.
   Document one installation path and rollback, then apply the proven binding
   contract to Claude and Hermes using their native capabilities; DSH remains a
   separate adapter gap. Do not claim support from generated config alone.

Retirement also means no active documentation or acceptance test may recommend
executing historical V2 scripts to repair V3. The old dirty checkout contains the
active worktree and shared Git metadata: keep it until its edits are inventoried
and V3 can be moved safely to a standalone checkout. Any later source cleanup is
a reviewed change in the V3 branch, not recursive deletion of that parent or of
  private V2/test vaults. No V2 memory-format migration is being introduced.

Next small usability slice: expose the existing aliases and per-project
include/exclude controls in the workbench, without introducing another policy
store. Then verify a native linked-worktree episode and task relocation/reconnect,
before extending automatic bindings to other harnesses. The current global
adapter is Codex-only; Claude/Hermes retain their documented local bindings.

## Model routing

Named provider/model profiles select routes independently for extraction,
consolidation, a hook (e.g. `hook:codex.Stop`) or a skill
(e.g. `skill:weekly-review`). Each route has a primary, ordered fallbacks
and output limit. An absent override inherits the operation's route.
Profiles may use different providers, models, reasoning settings and local or
hosted endpoints. Local FTS recall needs no model; optional semantic retrieval
is a later processor.

Fallback is finite and logged. Provider quotas, server errors and connection
failures may select the next configured profile. Application budget exhaustion
stops work across profiles. No unconfigured provider receives data, and invalid
model IDs are not silently replaced by hardcoded defaults.

The UI edits these settings. Credentials use local environment references or
keys held only for the workbench session, with OpenAI/Claude/local presets and
live model discovery. The optional Codex subscription module now implements
official managed browser/device login with a separate account directory;
authenticated generation acceptance is still pending. Enabled trusted modules
can contribute provider presets using the documented provider contract.
OAuth is not a generic replacement for API keys. Persistent OS key storage,
password login, key creation/revocation and
remote access belong to the later administration slice. Credentials must not
appear in status, logs or configuration readback.

Daily calls/tokens cover all attempts. Currency caps need configured prices
and conservative reservations. Missing usage is not zero cost. Display the
difference between estimated and measured usage. Tests use mock providers;
live paid calls are not required to validate fallback.

## UI, scheduling and network

The optional local workbench provides Memory, Providers, Consolidation and
Activity, Local sources and Modules views. Ordinary configuration must not require editing JSON or
running admin CLI commands. Empty, disabled and error states must be truthful.

The UI saves one consolidation scope and interval, enables/disables it, runs
the browsing scope now and shows last/next execution, last-run scope and budget
state. Changing browsing scope never retargets the saved schedule. Scheduled work runs only
while the foreground workbench is open. Say so directly. Later OS-service
installation can keep it running after reboot.

Remote networking is planned, not part of this slice: remain loopback-only.
Later add per-client scopes, LAN/private-network deployment, Internet TLS with
OAuth/API keys, credentials rotation/revocation, access logs, backup/retention
controls and connection diagnostics. Use a maintained MCP HTTP SDK as an
optional dependency. The server owns its vault on local disk; clients do not
mount SQLite over the network.

## Admission and memory quality

Records carry scope, source, status and optional key/supersession. Stable core
occurrence IDs reuse their first result. Durable extraction receipts preserve
completed occurrence results and cross-event dedupe aliases without rerunning
the provider. Per-vault extraction locking rejects concurrent runs; partial
receipts retain completed admissions. A crash between a Markdown write and its
receipt commit still needs reconciliation before unattended ingestion is claimed.
A confidence number cannot grant authority. User statements and
verified outcomes may be admitted automatically; inference, disputed and
superseded content is excluded from default factual context. A source excerpt
supports traceability but does not prove a paraphrased claim.

A decision in one project is not universal. Shared recipes need scope-aware
abstraction. Recalled memories, exported skills and generated summaries are
derivative evidence and cannot corroborate themselves. Conflicts depend on
project, subject, conditions and date. Human review is reserved for exceptions.

## Verification

- Fix reproduced null-to-None MCP input and irrelevant context clipping.
- Test learn/recall/correct/forget episodes instead of fixed tool counts.
- Test finite fallback, malformed response, reservations and budget exhaustion.
- Test UI in desktop/mobile, persistence and unsafe cross-origin writes.
- Run V3 regression and installed-package smoke before integration.
- Verify real Codex/Hermes/Claude sessions before advertising support.
- Measure usefulness, intervention, duplicates, p50/p95, RSS, disk growth,
  calls/tokens and processes on representative hardware.

Code and `docs/development-status.md` distinguish delivered behavior from this
plan. PR #58 is the original alpha baseline; this work is on
`codex/v3-learning-workbench`. Fresh review replaces earlier readiness claims.
