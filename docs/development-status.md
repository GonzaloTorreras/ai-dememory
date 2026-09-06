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

- Existing save/readback, lazy Unicode FTS, review, default vault and module
  scaffold remain. Seven top-level commands; no default daemon or model call.
- Scoped evidenced learning, provisional inference, keyed replacement and undo.
  Retrieval includes global plus requested scope, excluding inactive records.
- MCP now has seven tools including learn/forget; strict typed input and
  query-relevant context excerpts fix reproduced baseline defects.
- Optional loopback workbench: memory/source management, provider and route
  forms, ordered fallbacks, daily budgets, metadata activity, consolidation UI.
- Responses/OpenAI-compatible adapters; environment credential references only.
  Durable reservations count fallback attempts. No hardcoded model catalog.
- Bounded conversation extraction, no model-controlled correction keys.
- Conservative unkeyed duplicate cleanup; optional global summary proposals.
- Persisted hourly interval controls, manual runs and global foreground schedule.
- One active plan: [roadmap](roadmap.md). [Workbench guide](workbench.md) separates
  delivered operations from future remote/harness features.

## Evidence for this slice

- Full V3 suite: 104 tests; 101 passed, three Windows symlink cases skipped.
  Independent review reran the same suite. Compilation and diff whitespace checks pass.
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
- Wheel built and installed without runtime dependencies into an isolated venv.
  Installed CLI executed setup/save/recall/enable from outside the checkout;
  installed workbench HTML/JS/CSS rendered and retrieved that synthetic memory.
  Wheel: 56,444 bytes, SHA-256
  `815dabe6ad15da7c95a1e777ef516254b7eb52d7e6702298d9e88e21305c2444`.
- Fresh read-only reviewer found three learning-integrity blockers; all fixed
  with regressions. Final assessment: no remaining blocker for local opt-in
  alpha, not a remote-service or harness-integration certification.
- No real paid/local model call, provider credential read, private-vault write
  or OS service installation was performed. Provider behavior is mocked evidence.

## Limits and next vertical slice

1. Add extraction occurrence receipts before automatic retries/ingestion.
   Stable core identities reuse their result, but changed candidate indexes and
   cross-event dedupe aliases are not fully retry-idempotent yet.
2. Deliver one real Codex episode: recall, learn a scoped lesson, reuse it in a
   second session, correct it and verify no feedback recapture. Then Hermes and
   Claude adapters; identify DSH before promising its compatibility.
3. Validate one configured local model and one selected cloud fallback, with
   visible budget accounting. Current adapters use API credentials, not a
   Codex/ChatGPT subscription or an assumed model alias.
4. Extend scoped summary handling and procedural skill tests based on actual
   examples. Current model summaries are global review proposals only.
5. Plan remote auth/TLS/API-key administration and two-host operation separately.
   Never expose the current loopback listener through a public port mapping.

Known alpha limits: synchronous jobs block dashboard requests while running;
only 100 active memories are inspected per consolidation pass; automatic
scheduling processes global scope only. Evidence labels from trusted MCP
clients are not truth verification. Power loss between two correction-file
replacements may need reconciliation. Budget prices are configured estimates,
not provider invoice enforcement. These are documented, not hidden by fake metrics.

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
