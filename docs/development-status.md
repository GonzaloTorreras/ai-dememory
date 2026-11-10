# Development status

Updated: 2026-11-10. Current handoff only; earlier receipts remain in Git history.
Private memory inventories, query fixtures and curation journals stay outside Git.

## Public baseline

- Public `main`: `bb442e83be0d45f633f7a4bb44c5cbce3a9f9394`, PR #59 merged.
- `v3.0.0a3` published under the former TestPyPI-only prerelease policy. Its
  [publisher run](https://github.com/GonzaloTorreras/ai-dememory/actions/runs/42803057204)
  and [GitHub release](https://github.com/GonzaloTorreras/ai-dememory/releases/tag/v3.0.0a3)
  passed. Production PyPI was deliberately skipped by that old workflow.
- Prior source suite: 337 tests, 332 passed / five expected Windows symlink skips;
  cross-platform CI and exact published-index installation passed.

## Current increment: recall and maintainer-led PyPI delivery

- Branch `codex/v3-recall-quality-review`, based on the public baseline above.
  The pre-existing untracked `build/` remains untouched.
- Candidate version `3.0.0a4`; publication is pending reviewed PR/main CI/tag.
  User explicitly chose production PyPI for reviewed alphas and standing
  maintainer ownership without repetitive confirmation.
- Final focused checks: 42 passed. Full source suite: 345 tests, 340 passed / five
  expected Windows symlink skips. Clean-wheel setup/save/accent-recall smoke
  passed outside the checkout with no dependencies or network.
- Accent folding aligns Latin query filler, snippets and matching
  details with SQLite. This fixes dropped relevant context, not semantic search
  or translation. Synthetic regressions reproduced the failures before changes.
- Existing Jev connector is present and matches the current TypeSafe Choice API.
  Retain its supported pinned model, optional module, scope consent, preview,
  shared budgets and shadow-only behavior. Reject a selected answer below the
  maximum reported probability, while allowing ties. No new SDK or connector.
- The rubric/cache identity changes with the stricter validator so pre-upgrade
  cached results cannot bypass it. Query deduplication retains SQLite-distinct
  terms in other scripts and multi-diacritic Latin letters.
- Clarified the existing ten-second deadline: cooperative timeout checks can
  overrun during blocking network I/O; there is no hard wall-clock process kill.
- Tag workflow now dispatches the standalone PyPI publisher automatically.
  Preserve exact identity, green-main CI, build-once checksums/attestations,
  ordinary environment approval and OIDC. No protection/credential change.
- Private reviewed curation and frozen-query replay run independently from the
  release. No private contents, identifiers or corpus-derived metrics are added
  to public artifacts. Package installation never performs corpus cleanup.

## Next legal action and remaining limits

Finish focused/full tests, isolated package acceptance and fresh exact-diff
review. Open/merge the green PR under standing authority, require main push CI,
then dispatch the approved tag tuple and follow the PyPI publisher to completion.
Record final public receipts in the PR; never call a dispatch a successful upload.

Candidate coverage for untranslated paraphrases remains lexical. Do not add
vectors or Jev reranking without a measured coverage/usefulness case. Preserve
original-language terms during capture and retain uncertainty rather than
inventing current facts. Jev live quality/billing acceptance is not claimed.
Remote service and full native Hermes/Claude acceptance remain later work in
[the sole roadmap](roadmap.md).

Already-running MCP clients retain old imports; reconnect/reopen after a package
upgrade. Do not terminate unrelated clients or restart Windows to update them.
