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
- The release check passed every contract gate. Its remaining warnings are the
  local doctor warning and the intentionally missing PR URL before PR creation.

CI, the PR-bound strict release check, and a fresh final reviewer remain
required after the branch is pushed and the PR exists.

## Release Blockers

1. No `2.1.0rc1` has been published and installed from TestPyPI.
2. Release/tag workflows have not yet been exercised for the 2.1 exact tuple.
3. Release-candidate identity is prepared locally but is not yet committed,
   reviewed, or present on the package index.
4. Repository tag creation protection and both Trusted Publisher identities
   must be verified before dispatch.
5. Stable documentation must not claim 2.1.0 until the stable artifact is
   actually published and verified.

## Next Legal Actions

1. Finish `BRG-014`, continuity docs, RC identity, and guards on this branch.
2. Run full validation and obtain a fresh read-only review.
3. Open and merge the RC PR only after exact-head CI and approval.
4. Tag/publish `v2.1.0rc1`, install it from TestPyPI, and record evidence.
5. Open a separate stable-prep PR for `2.1.0`, repeat review/CI, then tag and
   publish the exact stable tuple.
6. Resume the V3 frontier only after stable post-publish verification.
