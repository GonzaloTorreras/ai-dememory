# Development Status

Updated: 2026-08-05

This is a reproducible public-repository handoff, not release evidence by
itself. The lead integrator updates it only when state or verified evidence
changes.

## Canonical Checkout

- Public remote: `https://github.com/GonzaloTorreras/ai-dememory.git`
- Base: `origin/main`
- Current public `main`: `6be35adcefee80fee24f1226f83e208cc40f24cc`
- Active corrective branch: `codex/rc1-tag-validator`
- Stable package at task start: `2.0.0`
- Planned sequence: `2.1.0rc1` on TestPyPI, then `2.1.0` on PyPI

The former private checkout is historical input only. Its push URL is disabled
and none of its release evidence is reusable.

## Active Scope

- Task: `BRG-014`
- Batch: `B04a`
- Compatibility: V2-compatible release fix; no V3 gate claim
- Objective: remove the duplicate shell tag regex that rejected the valid PEP
  440 tag `v2.1.0rc1` before publishing the already merged candidate
- Owned paths: exact tagger workflow, publish guard/tests, release runbook,
  changelog and this durable handoff

Required invariants:

- existing `v*` tags reject deletion and non-fast-forward updates;
- release tag creation stays a manual exact-tuple workflow;
- a direct tag never triggers package publication;
- publication stays a second exact-tuple, environment-bound OIDC workflow;
- documentation must not claim a native Actions bypass that GitHub rejects for
  the current personal repository;
- `ai_release_guard.py` is the single source of truth for stable and PEP 440
  prerelease tag syntax, and it runs before every tag mutation.

## Historical Reconciliation

The historical worktree contained 460 dirty entries at audit time: 373 tracked
and 87 untracked. It must not be merged wholesale.

- Already public: recall hooks, MCP profiles, bounded resource policies,
  process-tree cleanup, scheduler hardening, public site, release workflows, and
  solo-maintainer review controls.
- Ported now: the `BRG-014` operational/personal onboarding separation and a
  sanitized public continuity/planning baseline.
- Future reviewed slices: `BRG-003`, `BRG-017`, `BRG-019`, and `MIG-001`.
- Planning only: the V3 visual/multiplatform architecture and external evidence
  gates.
- Excluded: `memories/**`, `inbox/**`, temporary analysis, reports, local paths,
  archive-bound hashes/receipts, old release identity, and deletions that would
  regress current public runtime, site, security, or workflows.

## Verified Evidence On This Branch

- `tests.test_onboarding`: 40 tests passed after contract separation.
- Planning, documentation, site, release identity, MCP identity, and installed
  smoke contracts: 85 targeted tests passed before the final full-suite run.
- Full native Windows suite: 654 tests passed with 51 environment-dependent
  skips.
- Package build smoke passed for `ai_dememory-2.1.0rc1` wheel and sdist,
  including the wheel namespace check and `twine check`.
- Isolated installed-package smoke passed across config-only setup,
  memory-only onboarding, the public CLI, maintenance, hooks, scheduler,
  recall, and stdio MCP surfaces. It verified the installed version and exact
  MCP RC identity.
- The planning JSON contract is now executable and validates schema shape,
  task/batch membership, dependencies, DAG cycles, the legal frontier,
  evidence paths, and ledger consistency.
- Exact staged diff whitespace, generated-artifact, secret, and Pages artifact
  checks passed on the consolidated snapshot.
- Pull request [#17](https://github.com/GonzaloTorreras/ai-dememory/pull/17) was
  independently reviewed, passed exact-head CI and Pages, and merged as
  `640322c560e19c10be9b168a17f28116b04f3312`.
- Main push CI run `31003339116` passed on that exact merge SHA. Its tree is
  identical to reviewed PR head `2ae3199e4ead219cea35338863460841d6473e5b`.
- Live ruleset inspection found deletion and non-fast-forward protection on
  `refs/tags/v*`. GitHub rejected the documented native Actions creation bypass
  with HTTP 422 because the repository has a personal owner. ADR 0261 records
  the corrected effective boundary.
- Pull request [#18](https://github.com/GonzaloTorreras/ai-dememory/pull/18)
  corrected that boundary and merged as
  `6be35adcefee80fee24f1226f83e208cc40f24cc`; main push CI run `31005007306`
  succeeded and the merge tree matched reviewed head
  `d439f3039c447ff27312db849cb543eca57454e5`.
- Exact tagger run `31005240878` failed closed before checkout or mutation.
  Its shell regex accepted SemVer-like suffixes but rejected the canonical PEP
  440 tag `v2.1.0rc1`, while `ai_release_guard.py` correctly requires that tag.
  No release tag or package was created.

## Release Blockers

1. No `2.1.0rc1` has been published and installed from TestPyPI.
2. The tagger validation mismatch requires a focused PR, green CI and fresh
   read-only review before the exact tuple can be retried.
3. The publisher workflow has not yet been exercised for the 2.1 exact tuple.
4. Both Trusted Publisher identities still require live verification through
   the exact RC and stable publication paths.
5. Stable documentation must not claim 2.1.0 until the stable artifact is
   actually published and verified.

## Next Legal Actions

1. Validate and open the focused tag-validator correction PR.
2. Wait for exact-head CI, obtain a fresh read-only `READY` review, post the
   exact-tuple receipt, and merge only with its expected head SHA.
3. Retry the exact `v2.1.0rc1` tagger, then separately publish it to TestPyPI,
   install it from the index, and record evidence.
4. Open a separate stable-prep PR for `2.1.0`, repeat review/CI, then tag and
   publish the exact stable tuple.
5. Resume the V3 frontier only after stable post-publish verification.
