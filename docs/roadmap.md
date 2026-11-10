# V3 development plan

This is the single active product plan. Updated 2026-11-10 after the
[memory audit](memory-quality-audit-2026-10-29.md): the quality slices are now
installed locally as `3.0.0a3`, with a first reversible cleanup and populated-scope
maintenance. Complete mixed-record reconciliation and measure current/history
retrieval before more ingestion, semantic reranking or networking. Jev remains
optional, disabled locally and shadow-only with mock acceptance.

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

Completed locally: the three [memory-quality slices](#now-memory-quality-weights-and-optional-jev).
The installed CLI, fresh MCP/hook and dashboard now include these fields/fixes.
The first cleanup preserved 154 originals, separated three useful claims and
retired 19 obsolete states from normal recall. The current sequence is:

1. Finish reviewed PR/main/tag publication of the installed `3.0.0a3` candidate.
2. Reconnect long-lived clients so they load the updated package; fresh-process
   acceptance already passes. Runtime identity must be checked, not assumed.
3. Continue the private manifest's mixed-record and scope reviews in bounded
   per-project batches; preserve originals and extract claims before expiry.
4. Observe the now-active daily all-project schedule and visible batch coverage.
5. Refine single-claim admission and bilingual/current/history replay. Validated
   extraction lifecycle, neutral omission and correction inheritance are delivered.
6. Evaluate optional Jev reranking against a labeled baseline; confidence ranking
   stays zero until measured. Live data/cost opt-in follows local fixtures.

The [audit](memory-quality-audit-2026-10-29.md) gives acceptance and recovery
criteria. It introduces no second backlog, DAG or command family. The table below
records earlier capabilities and integration coverage, not a competing sequence.

Earlier increment: show local project names across the workbench while retaining
opaque internal scope IDs. Automatic host binding records bounded display-only
names in the existing operational SQLite file; it does not create identity
bindings, change canonical memories or scan conversations. Worktrees share the
common project name; same-name folders remain separate. Unknown historical
scopes become named when their project is used again.

Previous increment: `setup --with-codex --with-schedule --yes` installs the optional
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

## Global V3 installation: delivered baseline and remaining acceptance

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
   V3 alpha `3.0.0a2` is on TestPyPI, not production PyPI; an unpinned public
   package install is not this artifact.
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
   losing memory. Display-only names in operational state do not constitute a
   discovery/binding registry and cannot affect this resolver. Give projectless task
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

After the memory-quality slices, expose the existing aliases and per-project
include/exclude controls in the workbench, without introducing another policy
store. Verify a native linked-worktree episode and task relocation/reconnect
before extending automatic bindings to other harnesses. The current global
adapter is Codex-only; Claude/Hermes retain their documented local bindings.

## Now: memory quality, weights and optional Jev

### Baseline and boundaries

The reviewed source at `61788c0` has no importance/confidence fields. Retrieval
uses lexical FTS with OR over the first 20 tokens and no meaningful-match floor.
Its `bm25(memory_fts, 4.0, 1.0)` weights the unindexed ID column, not the title as
intended. Short useful prompts can be skipped by the harness, and snippets can
center on an uninformative word. Fix these in code, not with a model. Lexical
search also misses cross-language equivalents; stopwords cannot translate a query.

Admission records source labels/excerpts, but a host-supplied `verified_outcome`
is not independent verification. Execution receipts and lasting lessons share
one record shape. Consolidation cleans exact duplicates in one scope; generated
summary proposals are global-only. A schedule can target an empty scope while
projects contain useful memory. Direct host MCP learning needs no separate
DeMemory provider; provider-job usage is not total host-model consumption.

Reuse `models.py`, `vault.py`, `search.py`, `jobs.py`, module/provider settings
and the workbench. No new top-level command, database, daemon, vector store,
V2 reader or gate DAG. Optional canonical metadata lives in Markdown; search
remains disposable and job accounting durable. No bulk vault rewrite on upgrade.

### 1. Useful recall with explainable importance and confidence

Status: implemented locally, with confidence weighting deliberately locked at
zero and host importance advisory. See development status for tested evidence.

**Outcome:** save a lesson, edit its importance in the UI and retrieve the right
passage in a new conversation, with an explanation of why it was selected.

- Fix FTS column weights to ID/title/body `0, 4, 1`, following
  [SQLite's column-weight semantics](https://www.sqlite.org/fts5.html#the_bm25_function).
  Deduplicate/filter uninformative query terms before the limit; preserve identifiers,
  negations and useful short questions. Center snippets on informative whole-token
  matches. Return empty context when nothing meaningfully qualifies.
- Add optional `importance` (`low`, `normal`, `high`; absent means `normal`) and
  a bounded confidence assessment to memory/API metadata. UI edits, MCP learning
  and manual save share validation. Record setting origin; automatic importance
  remains a suggestion unless enabled and cannot overwrite a user's setting.

  | Dimension | Meaning | Default / authority |
  | --- | --- | --- |
  | Relevance | How well this passage answers this query | Per-query, never permanent truth |
  | Importance | How useful it is to retain/surface this lesson | Normal; user setting wins |
  | Evidence confidence | Estimated support for this claim in its cited evidence | Unassessed, not zero or verified |
  | Evaluator certainty | Concentration of the evaluator's answer distribution | Diagnostic, not factual support |
  | Status and validity | Whether the record may enter factual context | Enforced before ranking |

- Assessments name their method, claim/evidence revision and, for model judgments,
  model/rubric versions. Editing the claim/evidence invalidates the assessment.
  Manual source confirmation is a label, not a fabricated probability of 1.
  Arbitrary host self-scores are advisory: native MCP provenance authenticates
  neither their semantics nor a probability, so they cannot enter ranking.
- Use a bounded modifier, not adaptive rewards. After scope/status/validity and
  meaningful-match filtering, let `B = -bm25(...)` (higher is better),
  `I = 0 / 0.5 / 1` for importance and `C` an eligible evidence-support estimate
  (`0.5` neutral when absent/stale/unvalidated):
  `rank = B * (1 + w_importance * (2*I - 1) + w_confidence * (2*C - 1))`.
  Proposed defaults: `w_importance=0.15`, `w_confidence=0`; both nonnegative,
  their sum at most `0.25`. Reject nonfinite/out-of-range settings. These are
  testable starting values, not measured optima. Compare scores only within one
  query; BM25 is not a probability. No weight admits an irrelevant, provisional,
  superseded or expired record. Recall/copy counts confer no bonus.
  Apply weighted ordering over eligible matches before the final result limit,
  not just to the rows returned by today's lexical top-k. Project required
  metadata into the disposable index; avoid a full Markdown scan per query.
- Confidence weighting becomes opt-in only after assessor-specific evaluation
  below. Initially it stays neutral and the UI says "not assessed". Existing
  explicit keyed corrections need neither Jev nor a second review. Expose
  importance, assessment origin/freshness and reset in the memory editor; keep
  the two bounded weights in advanced settings. Recall details show matching
  terms and adjustments, never "probability this memory is true".

Acceptance: UI edit -> Markdown -> rebuilt index -> native scoped recall;
title/body weights, useful term after filler, short questions, missing metadata,
stale assessments, negative evidence and no-match cases. Include a relevant
boosted record initially just outside lexical top-k; irrelevant high-priority
records stay out. Correction/undo and project isolation still pass. Spanish/
English fixtures expose the language gap; do not claim translation from FTS fixes.

### 2. Less noise and consolidation that reaches the right projects

Local implementation complete: explicit lifecycle, scoped review and a rotating
three-scope batch reuse existing storage/jobs. Project model summaries require
separate opt-in. See development status for acceptance and remaining live gates.

**Outcome:** temporary execution history stops drowning out reusable lessons;
one visible schedule maintains the projects the user actually selected.

- Add optional `memory_kind` (`durable`, `episode`, `unspecified`) and explicit
  `expires_at`; absent fields preserve current V3 behavior. An episode is a dated
  result/status; a durable record may also expire. Never infer expiry from a
  vague date or classify old records automatically during installation.
- Exclude expired records from default factual recall, retaining inspectable
  history. Offer a reversible episode-age window in UI, initially off, distinct
  from claim validity. Dates/time zones are checked in Python. No physical delete
  or new archive subsystem. Remembered authorization never grants permission now.
- Keep one schedule/cadence/job owner, adding explicit selected scopes or "all
  project scopes"; global is a separate opt-in. Show target counts, no-op reasons
  and per-scope progress. Visit scopes separately with a bounded persistent
  cursor and shared budget/lock; restart or a large scope must not starve others.
  Never combine projects into global memory. Existing fixed-scope schedules stay
  unchanged until the user edits them.
- Give existing proposals an enforced scope before enabling project summaries.
  Exact dedupe/expiry filtering stays model-free; a configured text provider may
  suggest a concise source-linked summary, not overwrite originals automatically.
  Refuse stale summary acceptance after input correction. Routine explicit
  learning remains automatic; uncertain synthesis, not every fact, is reviewable.
- Prefer one claim per learning and enough literal context to interpret evidence
  (a bare year/number usually does not suffice). Use existing key/supersession
  for explicit changes to the same identified subject. Different entities,
  conditions or dates are not automatic contradictions. A summary cannot
  corroborate itself; do not silently merge semantic lookalikes.

Acceptance: empty global plus two populated project scopes; pause/restart,
fairness, concurrent UI/OS-task jobs, shared budgets, expiry/undo, correction after
proposal creation and same-value/different-entity cases. Repeated cleanup
converges, originals remain inspectable and no route means zero model calls.
This slice does not scan conversation history.

### 3. Optional Jev judgment module, not a second memory engine

Local implementation: manual shadow evaluation in the existing dashboard, with
mock-provider acceptance. Live quality calibration and real credential/billing
acceptance remain separate; no automated ranking/admission effect is enabled.

**Outcome:** enable a dashboard module, evaluate a small candidate against its
evidence, inspect the verdict/cost and disable it without breaking memory.
Initially shadow-only: no effect on admission, canonical text, rank or corrections.

- Implement `jev` through lazy modules, off by default. Add only the small typed
  `judge` capability needed here. The current provider plugin requires `generate`;
  do not fake that method for Jev. Extraction/summary drafting keep independent
  generative routes. Only judgment-capable profiles are judgment fallbacks.
- Use the official [System One API](https://docs.typesafe.ai/api), not an
  OpenAI-compatible text endpoint. Pin the evaluated model (currently
  `jev-1.13.0`, [models checked 2026-09-19](https://docs.typesafe.ai/models)).
  No SDK dependency/import in the disabled path and no Node runtime.
- Judge support from the bounded claim + cited evidence only, with `Choice`
  for `supports / contradicts / insufficient`. In a separate request, compare
  with a few same-scope candidates using `same claim / update / conflict /
  unrelated / unknown`. Existing memories must never enter the support request
  as corroboration. Optional `Score` can suggest low/normal/high usefulness
  with an explicit rubric. Batch independent questions only when their permitted
  evidence is identical; dependent decisions stay ordered in Python. Jev does
  not generate memories or require complete transcripts.
- Check literal quote inclusion in code when an authorized source window is
  available, then assess support. Otherwise label source authenticity unverified,
  not fabricated or validated. Adapt the
  [citation-check pattern](https://docs.typesafe.ai/cookbooks/citation_check),
  not its example thresholds/accuracy. Jev's
  [certainty statistic](https://docs.typesafe.ai/confidence) differs from
  `probabilities["supports"]`; neither proves real-world truth. Retain the verdict
  and provenance, not a naked "trust score".
- Reuse Modules/Providers/Consolidation UI: enablement, permitted operations/scopes,
  model, credential reference, finite fallback, daily calls/tokens/estimated cost
  and last result. Accounting covers all attempts. Missing usage is not free.
  Suggested starting limits: 3 API attempts total per job including retries,
  8,000 input characters per request, 10-second total request deadline and at
  most 1 retry within that deadline. Daily limits are explicit on activation.
  Show deferred/skipped work; no unbounded
  retry queue. No network calls on prompt-recall hooks.
- Send only opted-in scopes and sanitized excerpts. No credentials, paths or
  transcript payloads in diagnostics. Explain external processing:
  [no training does not mean zero retention](https://docs.typesafe.ai/legal).
  Preview first use; no private-vault export in development tests. Evidence is
  untrusted data, not policy. Numeric/date comparisons and permissions stay in
  code; [known limitations](https://docs.typesafe.ai/model-jaggedness/jev-1.13)
  include numbers, dates and adversarial input.
- Bounded decision receipts/cache reuse operational state, not raw prompts/
  responses or a new ledger. Key by local claim/evidence revision, model and
  rubric; invalidate on change. Disablement stops imports/calls and neutralizes
  Jev ranking adjustments. Failure/budget exhaustion retains the deterministic
  path and "unassessed", never synthetic success.

Acceptance: enabled UI-to-judgment episode with mock API, disabled zero-import/
zero-call checks, malformed responses, timeout/rate-limit/fallback/budget,
stale-cache invalidation and restart. Adversarial evidence cannot change scope,
permissions or canonical text. Test an existing memory that agrees with the
claim while its actual citation does not support it. Live evaluation needs
credentials and explicit data/cost opt-in; mock success is not model-quality proof.

### Evaluation, release and what stays later

Use one reusable fixture set, not a benchmark platform. Start with at least 30
labeled synthetic learning/recall/correction episodes covering Spanish/English,
current vs historical status, negation, insufficient excerpts, units, same-name
projects and unrelated queries. No private examples in public tests. Compare
baseline top-3 useful recall, irrelevant context characters, wrong replacements,
duplicates, interventions, p50/p95, RSS and calls/tokens after each slice. Report
counts, not an invented production failure probability.

Before confidence-weighted ranking, compare the same eligible candidates with
and without it on at least 100 held-out judgments/queries using the pinned
assessor/rubric. Report support precision/calibration by language and abstentions
as well as useful recall. Require five percentage points of useful top-3
improvement, no increase in unsupported factual hits, and no scope/provisional
leakage in the suite. These are proposed adoption gates, not verified benefits;
if unmet, leave the confidence weight zero. Model certainty never auto-promotes
inferences or resolves conflicts. Tune on separate cases, not the held-out set.

Each slice ships independently after focused review, full V3 tests, installed
package smoke and desktop/mobile checks for changed UI. No version bump or
publication in this planning change. Select the next alpha tag from merged/
tested scope only; merge, installation and publication stay separate gates.
Rollback: zero ranking weights, disable Jev, preserve canonical metadata and
durable receipts. Never erase operational SQLite to rebuild search.

Then resume project-controls UI, native harness acceptance and provider-login/
fallback coverage. Cross-language candidate generation/reranking needs a measured
follow-up: Jev cannot recover a memory absent from the lexical shortlist.
Procedural skills and remote/LAN admin remain later. No all-history ingestion,
new framework or model-driven autopromotion is implied.

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

The UI saves one consolidation interval with fixed, selected or all-project
targets, enables/disables it, runs the browsing scope now and shows bounded batch
progress, last/next execution, last-run scope and budget
state. Changing browsing scope never retargets the saved schedule. Scheduled
consolidation runs in the foreground workbench or through the optional current-user
Windows task; source ingestion still requires the workbench. Remote services and
other platforms' OS scheduling remain later work.

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
plan. PR #58 merged the alpha workbench and setup automation into public main;
the readable-project slice is on `codex/v3-readable-project-scopes`. Fresh review
replaces earlier readiness claims.
