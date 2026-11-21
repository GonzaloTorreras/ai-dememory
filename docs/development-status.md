# Development status

Updated: 2026-11-21. Current handoff only; prior receipts remain in Git history.
Private vault inventories, provider identities and replay data stay outside Git.

## Current increment: project-owned wiki

- Delivery-receipt branch: `codex/v3-a6-delivery-receipt`, isolated checkout
  `working/worktrees/project-wiki-v3`, based on public `origin/main` at
  `3834506fe2172ffabac820072252d4174824b743` (PRs #66 and #67 merged).
  The historical root checkout and other V3 worktree were not consolidated or reset.
- `3.0.0a6` is published on production PyPI and as a
  [GitHub prerelease](https://github.com/GonzaloTorreras/ai-dememory/releases/tag/v3.0.0a6).
  Source/tag target: `3834506fe2172ffabac820072252d4174824b743`.
  [Main CI](https://github.com/GonzaloTorreras/ai-dememory/actions/runs/44937209741),
  [tagger](https://github.com/GonzaloTorreras/ai-dememory/actions/runs/44937415412)
  and [publisher](https://github.com/GonzaloTorreras/ai-dememory/actions/runs/44937438041)
  passed. Normal environment approval/OIDC and the immutable annotated tag were retained.
  Scope and
  acceptance are in [the approved delivery plan](project-wiki-update.md);
  [the user guide](project-wiki.md) describes actual behavior, not future promises.
- Implemented: ordinary project Markdown, additive AGENTS guidance, bounded
  root/topic navigation, complete catalog, revision-bound edits, lifecycle-aware
  local recall, explicit read-only shared root, optional extractive librarian,
  UI settings/editor/preview and deterministic foreground maintenance.
- Local Codex/Claude hooks need client trust. Existing short-deadline global hooks
  stay local-only. New wiki prompt hooks reserve cleanup time for an explicitly
  consented provider; session-end only refreshes navigation, with no transcript
  read, model call, Stop continuation or resident worker.
- Review fixes: preserve whole excerpt conditions/provenance; recheck disabled
  module before provider dispatch; distinguish shared sources; show broken links;
  preserve unsaved UI drafts; tolerate an unavailable optional vault at project
  setup; keep empty navigation truthful. No private memory was imported.
- Regression: 419 tests, 413 passed / six expected Windows symlink skips.
  A stalled synthetic Codex child exits with its reader and scratch cleaned.
  Compilation, JavaScript syntax and diff checks pass.
- Earlier candidate wheel installed outside checkout: standalone CLI
  setup/save/recall/correct and both command-hook protocols pass, zero external
  calls. SHA256 `31152bdbaeffe078e394e50d051ee421c8b4dbdba81c5b5c146c0967d25f90b2`.
  One-page warm scan, 100 synthetic replays: p50 1.11 ms / p95 1.36 ms;
  this is not a production, cold-start or model-quality benchmark.
- UI QA: desktop 1280x900 and mobile 390x844, no horizontal overflow or console
  errors. Attach/template/save/correct/local recall, confirmed assisted selection
  with mocked transport and real broken-link rendering exercised. Browser plugin
  unavailable; existing Playwright integration used. Screenshots stay in scratch.
- Independent correctness/privacy readback passed for runtime head
  `80a7947f6d3c4d68faeb1f49a02224a907f685f0`: 77 focused tests (one expected
  symlink skip) and 50 provider/hook/privacy tests respectively. These were scoped
  read-only reviews, not a formal security scan.
- [PR #66](https://github.com/GonzaloTorreras/ai-dememory/pull/66) has a green
  [compatibility matrix](https://github.com/GonzaloTorreras/ai-dememory/actions/runs/44888152954)
  for Linux Python 3.11/3.13, macOS 3.12 and Windows 3.12 plus the installed CLI
  flow. Final head `897821b08a7eaeb7e996d0a14653693a33efdc46` passed fresh
  read-only review and [receipt CI](https://github.com/GonzaloTorreras/ai-dememory/actions/runs/44888365715)
  before merge.
  The synthetic QA server was stopped; no owned provider reader remains.
  Other open PRs #63/#64/#65 are not part of this branch.

## Published artifact and local acceptance

- Published wheel SHA256:
  `69378f48e5a42f1c97942a151d2d8bf8733b512403b7229d8756dd706e7c5f48`.
  Published sdist SHA256:
  `9bdcab637aff2e31dcfb53d3fa88472a2d86c009afcd08f2c18784999f86b36d`.
  PyPI metadata, downloaded wheel and GitHub SHA256SUMS agree. These are the
  release artifacts, not the earlier candidate wheel.
- The verified published wheel is installed in the existing local runtime.
  Fresh global CLI reports a6; the launcher, selected vault and canonical memory
  remain intact. No credential copying or private-vault export was performed.
- Installed dashboard: loopback HTTP, wiki load/edit/revision/save/recall and
  navigation maintenance pass. Desktop 1280x900/mobile 390x844 have no horizontal
  overflow, framework overlay or console warning/error. Only public synthetic
  wiki content was used; no external model call was made by the dashboard test.
- Native Codex `hooks/list` confirms enabled, trusted user SessionStart and
  UserPromptSubmit hooks. The installed command hook returns bounded attributed
  synthetic wiki context with a separate no-vault configuration; owned checker
  children exit. This is not a claim of a full private-vault model round trip.
- The first native model test used ignore-user-config and returned NOT_FOUND
  with hooks both off/on; it did not establish native injection. The follow-up
  real-configuration model test was blocked by security policy because private
  vault content might be injected. It was not bypassed; local metadata and
  synthetic-only checks were completed instead. Full real-config model
  acceptance requires explicit approval of that data boundary or a user-run test.
- Long-lived MCP clients retain old imported modules until reconnecting. Fresh
  CLI/hooks use the upgraded package; restarting Windows is not required.

## Prior public baseline / a5 delivery receipt

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

## Prior increment: bilingual evidence and Jev metadata skills

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

## Prior Jev acceptance boundary

The a5 full-suite, clean-wheel, review and publication receipts belong to that
release, not to this wiki candidate. Do not reuse them as proof of current native
client acceptance or model efficacy. Credentials are never extracted or copied;
public synthetic pilots do not authorize private-memory processing.

Keep scopes/automation off until explicitly configured. Do not add semantic
fallback infrastructure merely because language tagging exists. See
[measurement and limitations](bilingual-recall.md) and [the sole roadmap](roadmap.md).
