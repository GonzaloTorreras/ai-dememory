# Development status

Updated: 2026-11-10. Current handoff only; prior receipts remain in Git history.
Private vault inventories, provider identities and replay data stay outside Git.

## Public baseline

- Base `main`: `c12de9d3abda80d42b1e5a0d9c89c844e8e7b361`; PR #60 merged.
- `3.0.0a4` is on production PyPI. Tag→standalone-publisher→OIDC→PyPI and exact
  index installation passed in [run 42808325543](https://github.com/GonzaloTorreras/ai-dememory/actions/runs/42808325543).
- Its independently reviewed source had 345 tests, 340 passed / five expected
  Windows symlink skips. The default product remains dependency-free and passive.

## Current increment: bilingual evidence and Jev metadata skills

- Branch `codex/v3-bilingual-jev-skills`, source version `3.0.0a5`.
  Pre-existing untracked `build/` is preserved.
- Existing FTS now projects literal evidence at lower weight. Source-only hits
  need every informative term; scopes/lifecycle still filter first. An explicit
  retrieval switch restores title/body-only matching. No translation service.
- Independent synthetic holdout: source vocabulary 0/6→6/6, translation-only
  ceiling remains 0/4, wrong-constraint controls 0/2 added matches. This is not a
  production quality percentage or a Jev efficacy result.
- Per-module settings use the existing settings file and optional module-owned
  validation. Jev has independent language/usefulness/recall-tag switches,
  configurable language labels and an optional archive purpose.
- Manual language/usefulness assessments preview the exact claim and settings.
  They need no source excerpt because they do not verify truth. Enabled questions
  are batched through existing provider budgets/fallbacks.
- Optional automatic new-memory assessment reuses the foreground workbench:
  one item/minute, baseline on activation/reconfiguration, exact per-ID receipts
  in existing operational SQLite, no core-write callbacks or native-hook network.
  Fail-fast assessment lock prevents duplicate concurrent spending. Missing
  credentials/budget wait; other failed chains require explicit manual retry.
- Recall reads revision/config-bound advisory metadata only, never a model. No
  canonical writes, priority changes, automatic rejection, reward or reranking.
- Public synthetic pilot previews eight fixed examples and measures live language
  and retention judgments against labels and a keep-all baseline. No private
  memories/purpose enter that request; mocks test transport/UI, not model quality.
- Full suite: 364 tests, 359 passed / five expected Windows symlink skips.
  Final focused checks: 40 passed. Clean wheel installed outside checkout with
  bilingual save/recall and optional-skill availability; disabled Jev remained
  unimported. Compilation, JavaScript syntax and diff checks pass.
- Backend/UI checks pass on synthetic data. Desktop 1280×900 and
  mobile 390×844 have no overflow or console errors; preview→assessment→recall
  and the public-pilot UI ran with mocked transport. Browser plugin unavailable,
  existing Playwright integration used. Screenshots are tool-managed scratch.

## Remaining acceptance / next action

Finish full suite after final fixes, isolated wheel smoke and fresh exact-head
review. Then green PR/main CI and ordinary maintainer-owned tag/PyPI workflow.
A live Jev receipt is still pending: session credentials remain in the running
workbench process and are never extracted/copied. Re-entry after a runtime
restart is required; do not claim mock pilot scores as real model gains.

Keep scopes/automation off until explicitly configured. Do not add semantic
fallback infrastructure merely because language tagging exists. See
[measurement and limitations](bilingual-recall.md) and [the sole roadmap](roadmap.md).
