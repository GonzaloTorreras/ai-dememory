# Development status

Updated: 2026-09-07

## Current line

- Worktree: `working/worktrees/product-reset-v3` under the historical checkout.
- Branch: `codex/v3-learning-workbench`, based on V3 alpha head
  `a04a0cdeb21ece09727bf242a2c2c2e8c6a54280`.
- Public base for the reset: `e7f823ecf223d544b1f2f4cd909fbc42afb3aea3`.
- Source: `3.0.0a1`, still unpublished. No version, release tag or package publication.
- PR #58 is the previous alpha baseline, not an updated readiness receipt for
  this branch. No merge or new hosted CI is claimed for this local slice.
- The large dirty historical V2 checkout was not merged or cleaned wholesale.
- No V2 migration or compatibility work.

## Implemented local alpha

### Current increment: conversation browser and source schedules

- Based on local `4189345`; no version/publication change.
- Codex sessions folder and adjacent title-index schema verified locally without
  exposing conversation text in diagnostic output. Bounded listing returned 100
  recent conversations, 96 with readable titles; no model call or memory write.
- Recent-first scan, titles/workspaces, subagent/guardian exclusion, native user
  event preference, complete bounded provenance metadata and large-log tail windows.
- Inline accordion previews, ten-item checkbox batches with expiry preflight,
  shared scope selector and scope-change invalidation. Results remain per item.
- Independent Codex/Claude module switches preserve the other existing client.
- Opt-in source rules store explicit folder/harness/scope/interval, support manual
  run/pause/resume/removal and reuse provider routes/budgets/receipts. One changed
  human window per run; assistant-only appends do not spend another model call.
- No live automatic extraction was enabled on personal sessions. Browser tests
  use synthetic conversations and a fixture model; real provider acceptance is
  still distinct. This does not implement exhaustive historical backfill.
- Final suite: 177 tests, 173 passed and four Windows symlink skips. Node syntax
  and whitespace checks pass. Fresh read-only review validated parser provenance,
  schedule deduplication, scope/route boundaries and batch preflight. Schedule
  state now has 128 fixed-size fingerprints per rule and a checked 1 MB writer cap.
- Browser acceptance at 1440x1080 and 390x844: titled list, inline preview,
  two-conversation extraction to `project:qa`, scope-change invalidation and paused
  schedule creation. No overflow; one early fixture-engine schema error was
  corrected in the QA fixture, with subsequent extraction passing.
- Installation artifact: 93,011 bytes; SHA-256
  `a0e5846ce5e65dc5d1a35a5ad4112736ae7be22b13656d29e2ee98f68d474e00`.
  Installed into the existing isolated runtime and verified outside the repo;
  workbench restarted on 127.0.0.1:8765. Existing vault/config preserved; no
  personal-history schedule enabled. Synthetic QA server stopped.

### Latest local slice: guided providers and optional sources

- Based on local commit `e549c15`; source remains unpublished `3.0.0a1`.
- Guided presets, live provider model discovery, explained profile aliases and
  conditional protocol fields; no hardcoded catalog or implicit generation.
- Optional Codex managed browser/device login with isolated account storage,
  ephemeral tool-disabled generation, advertised reasoning validation and owned
  child cleanup. Subscription-to-remote-API fallback is blocked; local fallback
  remains available. USD accounting does not represent purchased Codex credits.
- Optional bounded source preview: Codex/Claude/Pi, generic exports, raw DSH and
  checkpointed Hermes snapshots. No background ingestion, active Hermes WAL or
  DSH compression support. Preview-to-extract binds exact text, scope and routes.
- Existing trusted modules can provide model adapters and dashboard alternatives.
  No arbitrary dashboard script injection or visual extension editor.
- Final full suite: 169 tests, 165 passed and four Windows symlink skips. Node
  syntax and diff whitespace checks passed. Earlier repeated Windows TCP aborts
  on denied POSTs were reproduced and fixed by consuming bounded request bytes
  before authorization, without parsing JSON or executing actions beforehand.
  Forty denied POSTs and invalid JSON rejection pass; a premature socket close
  in the credential test was also corrected to stop and join the server thread.
- Browser QA: synthetic loopback model catalog returned two IDs; selected model
  and route saved; user-only folder preview extracted one evidenced memory end
  to end. OpenAI preset hid protocol fields; mobile/desktop showed no document
  overflow or console errors. No real conversation, API credential or paid call.
- Codex native no-login probe verified isolated account/config and model catalog;
  child and reader stopped. Thirteen subprocess fixture tests cover managed login,
  timeout cleanup and generation. Live authenticated generation remains pending.
- Fresh independent read-only review: 49 focused tests, one Windows skip; no
  remaining blocker found. Earlier test/wheel receipts below are historical.
- Updated isolated installation from an 86,082-byte wheel, SHA-256
  `e47321776faeb8fcc5ecf6b3de19a7dbec14cd144b629369abaa56fad9943d59`.
  Installed imports/version verified outside both source checkouts (`3.0.0a1`).
  The idle test workbench alone was stopped and restarted on loopback port 8765;
  its test-vault binding and previously enabled modules were preserved. New
  sources/subscription modules remain disabled. No shared Codex account changed.

- Existing save/readback, lazy Unicode FTS, review, default vault and module
  scaffold remain. Seven top-level commands; no default daemon or model call.
- Scoped evidenced learning, provisional inference, keyed replacement and undo.
  Retrieval includes global plus requested scope, excluding inactive records.
- MCP now has seven tools including learn/forget; strict typed input and
  query-relevant context excerpts fix reproduced baseline defects.
- Optional loopback workbench: memory/source management, provider and route
  forms, ordered fallbacks, daily budgets, metadata activity, consolidation UI.
- Responses, Anthropic Messages and OpenAI-compatible adapters; credential
  environment references or workbench-session-only API keys, never vault secrets.
  Durable reservations count fallback attempts. No hardcoded model catalog.
- Bounded conversation extraction, no model-controlled correction keys.
- Durable extraction occurrence receipts: completed retries avoid provider
  calls and preserve aliases, zero-result admissions and original record IDs.
- Project-local Codex/Claude installer, scope-bound MCP and fail-open
  UserPromptSubmit recall. No transcript reader, Stop hook or extra model call.
  Native client acceptance is distinct from installed protocol tests below.
- Conservative unkeyed duplicate cleanup; optional global summary proposals.
- Persisted hourly interval controls, manual runs and global foreground schedule.
- One active plan: [roadmap](roadmap.md). [Workbench guide](workbench.md) separates
  delivered operations from future remote/harness features.

## Evidence for this slice

- Full V3 suite: 130 tests; 127 passed, three Windows symlink cases skipped.
  Compilation and diff whitespace checks pass. The final CLI-help regression
  verifies that enabling the installer points to usable installation help.
- Focused tests cover source/scope/undo, relevant context, null MCP input,
  generated-key rejection, correction-safe dedupe, 429/timeout fallback,
  concurrent budget reservations, credentials isolation and malformed responses.
- HTTP tests exercise real loopback requests, Host/Origin/token rejection,
  Unicode saves, settings persistence, scheduling, scoped writes/forget and
  extraction through a mocked provider. Test server threads are joined.
- Real browser QA at 1440x1080 and 390x844: provider/route/budget persistence,
  unsaved-settings preservation, scoped save/correct/undo, schedule/run-now,
  responsive forms and dialogs. Fixed modern HTML pattern syntax and mobile
  overflow; final inspected pages have no document overflow or console errors.
- Visual comparison retained the white/emerald reference hierarchy, left
  navigation, route rows and restrained controls. Mobile intentionally wraps
  navigation and stacks forms. Empty provider state is real, not sample data.
- Previous workbench wheel built and installed without runtime dependencies into an isolated venv.
  Installed CLI executed setup/save/recall/enable from outside the checkout;
  installed workbench HTML/JS/CSS rendered and retrieved that synthetic memory.
  Wheel: 56,444 bytes, SHA-256
  `815dabe6ad15da7c95a1e777ef516254b7eb52d7e6702298d9e88e21305c2444`.
- Fresh read-only reviewer found three learning-integrity blockers; all fixed
  with regressions. Final assessment: no remaining blocker for local opt-in
  alpha, not a remote-service or harness-integration certification.
- No configured extraction-provider call, provider credential read, personal
  vault write or OS service installation was performed. Provider fallback still
  has mocked evidence; the Luna acceptance subagent uses Codex account usage.

## Installed integration acceptance

- User authorized an isolated PC installation, test vault and project-local
  Codex configuration. The existing global executable, client settings and
  personal vaults were not replaced. No package was published.
- Final integration wheel: 61,952 bytes, SHA-256
  `59ddb9c0d912553fa5d50c64ec4a0235855583cc63e3be6112ddf6edef3955d5`.
  Reinstalled successfully into the isolated runtime; installed enable/help
  readback passed. The original host launcher was already broken and remains
  untouched; the isolated executable is the tested entrypoint.
- A Luna subagent at `low` (its lowest supported effort) exercised the installed
  stdio MCP with synthetic data. Initialize, tool discovery, learn, duplicate
  retry, cross-scope rejection, correction and undo passed. A fresh process
  retrieved the saved fact; both MCP processes exited 0 with empty stderr.
- Ten invocations of the exact installed hook entrypoint returned 0 and
  additional context with the saved fact, excluding provisional inference.
  Measured subprocess wall time: p50 567 ms, p95 598 ms on this PC. This is a
  small local sample, not a native Codex delivery or representative benchmark.
  All test-created processes were closed and waited for.
- Native Codex `exec` with `gpt-5.6-luna`/`low` was rejected by the server with
  “requires a newer version of Codex”. Installed CLI and current npm stable
  both reported 0.153.4. The failed probe was stopped; no alternate model or
  hook-trust bypass was used. Native delivery and `/hooks` trust remain pending.
- Claude project configuration is schema/unit tested, not live-session tested.
- Fresh focused read-only review: 41 tests passed and no remaining blocker for
  isolated local-alpha testing. Do not interpret this as native client certification.

## Limits and next vertical slice

Latest provider-config slice (after `bb226ec`):

- Cloud HTTPS was already allowed, but the generic localhost-oriented form
  obscured it and Anthropic's protocol was missing. Added OpenAI/Claude/local/
  custom presets, native Messages requests, explicit auth modes and safe UI retry.
- Session keys remain in RAM and are bound to exact provider kind, endpoint and
  auth mode. Submissions carry the expected identity so an intervening edit
  cannot rebind a key. Changes/removal/shutdown invalidate them; state reports
  presence only. Environment credentials still support restartable scheduling.
- Direct OAuth login, workload federation and OS keychain persistence are not
  implemented. MCP clients keep their own supported subscription authentication.
- 24 focused provider/HTTP tests passed; fresh read-only review's two concrete
  blockers were fixed and re-reviewed. Full suite and JS syntax/compile/diff
  checks passed. No real credentials or live model requests were used.
- Playwright at loopback port 8872 verified OpenAI session-key save, Claude env
  config, custom HTTPS, refresh persistence, clearing a key, invalid-key retry
  and invalid-endpoint retry. 1440x1080 and 390x844 had no horizontal overflow;
  desktop/mobile captures were inspected in memory. Browser plugin skill was
  unavailable, so the Playwright connector was used. Expected 400 responses
  exercised validation; clean reload had no console errors or error overlays.
- Updated isolated PC wheel: 65,136 bytes, SHA-256
  `747be3fb2bc787759ecee86f278522084d417070d1865ef8761304e8802d0abb`.
  Installed asset/import smoke passed. Windows initially blocked its running
  launcher; the old package was restored, the exact idle test-vault workbench
  processes were verified/stopped, then reinstall succeeded. No unrelated
  processes or vault settings were changed. Restart workbench to use this build.
  QA server/browser were stopped; no package publication or hosted CI claimed.

1. Complete native Codex acceptance once a compatible client/model route is
   available; review and trust the exact generated hook via the client.
2. Deliver one real Codex episode: recall, learn a scoped lesson, reuse it in a
   second session, correct it and verify no feedback recapture. Then Hermes and
   Claude adapters; DSH is identified, but compressed session acceptance is pending.
3. Validate one configured local model and one selected cloud fallback, with
   visible budget accounting, then complete explicit Codex subscription login
   and one synthetic authenticated extraction. Do not substitute an assumed alias.
4. Extend scoped summary handling and procedural skill tests based on actual
   examples. Current model summaries are global review proposals only.
5. Plan remote auth/TLS/API-key administration and two-host operation separately.
   Never expose the current loopback listener through a public port mapping.

Known alpha limits: synchronous jobs block dashboard requests while running;
only 100 active memories are inspected per consolidation pass; automatic
scheduling processes global scope only. Evidence labels from trusted MCP
clients are not truth verification. Power loss between two correction-file
replacements may need reconciliation. Budget prices are configured estimates,
not provider invoice enforcement. A crash between a Markdown admission and its
durable extraction receipt can require reconciliation; partial retries do not
make the two stores transactional. These are documented, not hidden by fake metrics.

## Historical baseline evidence

The previous seven-slice alpha had 61 tests (58 passing locally, three Windows
symlink skips) and successful cross-platform CI, including
[run 33559917823](https://github.com/GonzaloTorreras/ai-dememory/actions/runs/33559917823)
at `0474dc9`. Earlier install/scaffold and read-only status fixes are preserved
in Git history. Those results do not certify the newer learning workbench.

## Integration boundary

Local review and tests are complete for this slice. Before a PR is marked ready,
refresh exact base/head and hosted CI. Merge, tag and publish remain separate
actions; no historical release evidence is reused. Rollback is disabling/stopping
workbench and reverting this feature branch; keep canonical memory and durable
operational receipts backed up, never delete them as a search rebuild.
