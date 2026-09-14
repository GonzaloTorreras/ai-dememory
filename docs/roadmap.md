# V3 development plan

This is the single active product plan. Updated 2026-09-14 after the V2/V3
audit and the request for autonomous, modular, multi-harness memory.

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
  foreground process with local web UI and optional scheduled jobs.
- Keep operational cursors, budget reservations and job receipts outside the
  disposable index. They must survive an index rebuild.
- No V2 migration, new gate DAG, per-function ADRs, adaptive ranking reward,
  default vectors or separate Node runtime.

## Delivery sequence

Latest local increment: readable Codex conversation titles/workspaces, internal
session filtering, accordion previews, multi-selection, shared scope selector,
independent Codex/Claude module switches and per-harness source schedules.
Codex now also has opt-in chronological history windows, persistent retry cursors,
folder pagination and UI progress. This remains bounded discovery, not exhaustive
historical consolidation. Hermes source reading also supports local live WAL,
session titles and bounded read transactions; it is not a native memory provider.
Next ingestion work should be driven by measured gaps: DSH compressed input,
Hermes conversation lineage and native cross-harness episodes.

Every row is a complete user-visible slice, not empty interfaces.

| Slice | Outcome | Acceptance |
| --- | --- | --- |
| Local learning workbench (implemented alpha) | Configure providers and ordered fallback, learn a scoped fact, retrieve its relevant passage, inspect activity, set consolidation interval and budgets in UI | Settings survive restart; mocked provider failure selects fallback within budget; invalid input creates no memory; inference stays provisional. Live model acceptance remains pending |
| Correction and hygiene (implemented alpha) | Explicit keyed replacement, exact unkeyed dedupe, undo, inactive-state filtering and durable extraction receipts | Completed extraction retries return original admissions without another provider call; correction wins only in its scope; history remains inspectable. Interrupted two-store writes remain a documented limit |
| Codex integration (native MCP episode verified; hook acceptance pending) | Scope-bound MCP tools, project-local installer and bounded prompt recall | Three native Luna sessions learned, recalled, corrected and undid a scoped synthetic lesson through the installed MCP. CLI compatibility is verified; automatic trusted-hook injection remains separate |
| Hermes and Claude | Native Hermes provider, Claude hooks/MCP, one extraction owner per origin | Cross-harness recall works; native caches do not reenter as new evidence |
| Incremental ingestion (Codex history implemented alpha) | Authorized native Codex deltas, occurrence receipts, durable byte cursors, bounded folder pagination and visible progress | Failed windows retain their exact range across append/restart; separate positions remain separate occurrences; no re-extraction on assistant-only activity. Native rotation/rewrite and other harnesses remain incomplete |
| Consolidation and skills | Reversible cleanup, evidence-backed procedural knowledge and tested skill export | Repeated runs converge; recipes work in a second case; executable capabilities have policy, tests and rollback |
| Remote service/admin (later) | HTTP MCP/event service on PC/Raspberry, LAN/Internet, admin UI | Identity-based scopes, TLS, revocation, two-host restart/replay and restore tested before exposure |

DSH is [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness).
The optional manual sources module now previews its plain JSONL, Codex/Claude/Pi
exports and Hermes databases (live local WAL or checkpointed snapshots).
Compressed DSH and Hermes lineage remain explicit gaps. The Hermes reader is
bounded recent-window extraction, not exhaustive unattended ingestion.

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

The UI selects consolidation interval, enables/disables it, runs it now and
shows last/next execution and budget state. Initially scheduled work runs only
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
