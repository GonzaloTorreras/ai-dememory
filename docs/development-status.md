# Development status

Updated: 2026-11-10. Current handoff only; prior receipts remain in Git history.
Private vault inventories, provider identities and replay data stay outside Git.

## Public baseline

- Published source: `9af5d6531134b0ccbabe936546657913a49780a8`; PR #61 merged.
- `3.0.0a5` is on production PyPI and is a GitHub prerelease. Main
  [CI](https://github.com/GonzaloTorreras/ai-dememory/actions/runs/42820733961),
  [tag](https://github.com/GonzaloTorreras/ai-dememory/actions/runs/42821045067) and
  [publisher](https://github.com/GonzaloTorreras/ai-dememory/actions/runs/42821084174)
  passed. Normal environment approval and OIDC were retained.
- Public wheel SHA256: `10b45b23f4ff2da56202f97b303e0074da0c7611a5bb36fd5209e6266fcaaead`.
  Downloads match PyPI JSON and GitHub SHA256SUMS. The exact published wheel is
  installed locally; fresh MCP reports `3.0.0a5`, lifecycle/expired-context and
  prompt-hook acceptance pass, and owned test children exit. Workbench HTTP is
  healthy. Long-lived clients must reconnect; they are not silently reloaded.
- The default product remains dependency-free and passive.

## Delivered increment: bilingual evidence and Jev metadata skills

- PR #61 completed on `codex/v3-bilingual-jev-skills`. The documentation receipt
  is on `codex/v3-a5-delivery-receipt`; pre-existing untracked `build/` is preserved.
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
- Review regression checks cover exact question consent, revocation before
  fallback, missing-credential/budget tails after a failed attempt and interleaved
  automatic workers. Confirmation and semantic cache identities are separate;
  automatic receipt checks and terminal writes share the assessment lock.
- Full suite: 368 tests, 363 passed / five expected Windows symlink skips.
  Final focused checks: 67 passed. Clean wheel installed outside checkout with
  bilingual save/recall and optional-skill availability; disabled Jev remained
  unimported. Compilation, JavaScript syntax and diff checks pass.
- Backend/UI checks pass on synthetic data. Desktop 1280×900 and
  mobile 390×844 have no overflow or console errors; preview→assessment→recall
  and the public-pilot UI ran with mocked transport. Browser plugin unavailable,
  existing Playwright integration used. Screenshots are tool-managed scratch.

## Remaining acceptance / next action

Full-suite, clean-wheel, exact-head independent correctness/privacy review and
publication acceptance are complete. Live Jev efficacy is still pending session
credential re-entry after the dashboard update. Credentials are never extracted
or copied; do not claim mock pilot scores as real model gains. Run only the
confirmed public synthetic pilot before considering any private-memory processing.

Keep scopes/automation off until explicitly configured. Do not add semantic
fallback infrastructure merely because language tagging exists. See
[measurement and limitations](bilingual-recall.md) and [the sole roadmap](roadmap.md).
