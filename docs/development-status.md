# Development Status

Updated: 2026-08-05

This is a reproducible public-repository handoff, not release evidence by
itself. The lead integrator updates it only when state or verified evidence
changes.

## Canonical Checkout

- Public remote: `https://github.com/GonzaloTorreras/ai-dememory.git`
- Base: `origin/main`
- Base SHA at release worktree creation:
  `a2210224dc8bb34df8ecb37ea711e3da80577b42`
- Active integration branch: `codex/release-2.1.0`
- Stable package at task start: `2.0.0`
- Planned sequence: `2.1.0rc1` on TestPyPI, then `2.1.0` on PyPI

The former private checkout is historical input only. Its push URL is disabled
and none of its release evidence is reusable.

## Active Scope

- Task: `BRG-014`
- Batch: `B04a`
- Compatibility: V2-compatible release fix; no V3 gate claim
- Objective: make `setup wizard` config-only and keep `onboard` memory-only
- Owned paths: onboarding/setup CLI, tests, install/site/plugin documentation,
  continuity and planning contracts

Required invariants:

- `setup wizard` writes only `.ai-dememory.toml`;
- `onboard` writes only reviewed personal/project Markdown;
- both structured flows require an exact preview fingerprint;
- decline, drift, conflicts, and incomplete rollback fail closed;
- neither flow installs MCP, hooks, providers, or scheduler jobs;
- `init --wizard` never invents or creates personal memory.

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
- Pull request [#17](https://github.com/GonzaloTorreras/ai-dememory/pull/17)
  exists for this branch. PR-bound strict release, MCP runtime, and MCP client
  smokes passed after generating the disposable local index used by CI.
- CI run `31000835426` and Pages run `31000835430` passed on candidate commit
  `c7c87eac3f0f8d137bb05c5da5f68822a4ec5601`, including Docker and the
  Windows/macOS/Linux Python 3.11-3.13 matrix.
- The first post-PR reviewer found no code, security, or CI blocker and required
  only this stale-handoff correction. Because this correction creates a new PR
  head, exact-head CI and a fresh read-only review must pass again before merge.

## Release Blockers

1. No `2.1.0rc1` has been published and installed from TestPyPI.
2. Release/tag workflows have not yet been exercised for the 2.1 exact tuple.
3. Release-candidate identity is committed and code-reviewed in PR #17, but the
   PR is not yet merged and the candidate is not present on the package index.
4. Repository tag creation protection and both Trusted Publisher identities
   must be verified before dispatch.
5. Stable documentation must not claim 2.1.0 until the stable artifact is
   actually published and verified.

## Next Legal Actions

1. Push this documentation-only handoff correction and update PR #17 with its
   exact head and completed evidence.
2. Wait for exact-head CI and obtain a fresh read-only `READY` review.
3. Post the exact-tuple solo-maintainer receipt, mark PR #17 ready, and merge
   only with its expected head SHA.
4. Tag/publish `v2.1.0rc1`, install it from TestPyPI, and record evidence.
5. Open a separate stable-prep PR for `2.1.0`, repeat review/CI, then tag and
   publish the exact stable tuple.
6. Resume the V3 frontier only after stable post-publish verification.
