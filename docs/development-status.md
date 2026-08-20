# Development Status

Updated: 2026-08-18

This is a reproducible public-repository handoff, not release evidence by
itself. The lead integrator updates it only when state or verified evidence
changes.

## Canonical Checkout

- Public remote: `https://github.com/GonzaloTorreras/ai-dememory.git`
- Base and current public `main`:
  `c5ee8b55b12d266342ef7db7b4fa10d4459154ec`
- Active release branch: `codex/release-2.1.0-stable`
- Published stable package at branch start: `2.0.0`
- Verified candidate: `2.1.0rc1` on TestPyPI and GitHub Releases
- Target: cumulative stable `2.1.0` on PyPI

The former private checkout is historical input only. Its push URL is disabled
and none of its memories, receipts, pins, paths or release evidence is reusable.

## Active Scope

- Completed product task: `BRG-014`
- Completed batch: `B04a`
- Release objective: promote the verified V2.1 behavior as exact stable
  `2.1.0`, with deterministic notes covering the net public history since
  `v2.0.0`
- Owned paths: stable version identities, changelog and release-note contract,
  user documentation/site, planning frontier and this durable handoff
- Compatibility: release-only closure; no V3 runtime or external-gate claim

Required invariants:

- Python 3.11+ remains the only domain and headless runtime; Node is not an
  installation or background dependency;
- Markdown remains canonical and real vault data remains outside the public
  repository and installed executable;
- setup policy and optional reviewed durable onboarding stay separate;
- public/core MCP defaults remain bounded while explicit `admin` preserves the
  historical complete surface;
- a release body is generated deterministically from the exact dated changelog
  section and links the complete public comparison;
- tag creation and package publication remain separate exact-tuple workflows;
- stable publication requires the already completed TestPyPI RC evidence,
  exact-head review, green CI, immutable tag, OIDC, post-index installation and
  GitHub Release assets.

## Historical Reconciliation

The historical worktree contained 460 dirty entries at audit time: 373 tracked
and 87 untracked. It must not be merged wholesale.

- Public net history since 2.0.0 includes contextual recall, bounded autonomy,
  process cleanup, MCP profiles, one-session setup, public documentation,
  security policy, Pages delivery, release hardening and continuity contracts.
- Superseded auto-approval behavior is omitted from product claims; the later
  exact-head solo-maintainer receipt model is the effective control.
- Planning-only V3 and MemPalace-derived ideas remain research until their
  public task dependencies and evidence gates complete.
- Excluded material remains excluded: private `memories/**`, `inbox/**`, local
  reports, paths, hashes/receipts tied to an archive, credentials and stale
  release identity.

## Verified Release-Candidate Evidence

- PR [#17](https://github.com/GonzaloTorreras/ai-dememory/pull/17)
  consolidated the public V2.1 implementation and merged as
  `640322c560e19c10be9b168a17f28116b04f3312` after independent review, exact
  CI and Pages checks.
- PR [#18](https://github.com/GonzaloTorreras/ai-dememory/pull/18) corrected
  the personal-repository tag trust model and merged as
  `6be35adcefee80fee24f1226f83e208cc40f24cc`.
- PR [#19](https://github.com/GonzaloTorreras/ai-dememory/pull/19) centralized
  PEP 440 tag validation and merged as
  `c5ee8b55b12d266342ef7db7b4fa10d4459154ec`; main CI run `31006201172`
  passed and its tree matched reviewed head `6102f7e001412fd1acce28b082e33436679ae8c4`.
- Annotated immutable tag `v2.1.0rc1` points exactly to `c5ee8b55...`.
- Release workflow
  [31006564196](https://github.com/GonzaloTorreras/ai-dememory/actions/runs/31006564196)
  passed validation, 654-test/runtime coverage, isolated wheel/sdist smoke,
  Docker smoke, build-once checksums, artifact attestation, environment-gated
  TestPyPI OIDC publication, post-index installation and GitHub prerelease
  creation.
- TestPyPI serves `ai_dememory-2.1.0rc1-py3-none-any.whl` with SHA-256
  `7cb32d37a436f4c5a52684de5849e00abb06c6733db1d5fe6594353a073038ff` and
  `ai_dememory-2.1.0rc1.tar.gz` with SHA-256
  `cacd5339844ff4617a34525f8b5e335a3fdbeb9e560d7031a7d5a9d8ffde96db`.
- A second clean Windows environment installed `2.1.0rc1` directly from
  TestPyPI with cache disabled, produced a non-writing balanced wizard plan,
  negotiated MCP `2025-11-25`, returned server version `2.1.0rc1`, answered
  ping and left zero package-owned processes.

## Verified Stable-Branch Evidence

- The cumulative 2.1.0 changelog, exact package/plugin identities, deterministic
  release-note parser, user docs and static Pages content are complete on this
  branch. The documentation/site guard passes its source-derived release,
  profile, link, security and payload-budget contracts. The NotebookLM/Gemini
  Notebook analysis is recorded only as non-normative source-grounded query
  research; it does not change the task DAG or claim a shipped V3 runtime.
- Native discovery completes 755 tests with 51 environment-specific skips and
  no failures. Focused evidence also passes for the core memory tools (535 with
  45 skips), release identity (35), stable docs/site commands (54),
  onboarding/wizard (45), MCP profiles/lifecycle (21), planning contract (5)
  and the Pages artifact contract (14); isolated bytecode compilation passes.
- A clean temporary build produced exactly
  `ai_dememory-2.1.0-py3-none-any.whl` and `ai_dememory-2.1.0.tar.gz`; both pass
  namespace validation, isolated artifact installation and `twine check`.
  Their local pre-publication SHA-256 values are respectively
  `f8aaa7ad50a1576bd051ef32b47ce37bb898fcb4daaebeca602e19b4ba5dd8ec`
  and `54a2009490f727edebb2842f2167a4b21b02a4568acec784bb749631b28ff378`;
  CI must build once and establish the release-canonical hashes. Generated
  source metadata is removed afterward. Setuptools still emits non-fatal
  package-data discovery warnings for data-only template directories; both
  artifact smokes confirm that the packaged vault template remains complete.
- A no-cache clean virtual environment installed the exact 2.1.0 wheel, passed
  exact-version and mismatch checks, applied the fingerprint-bound balanced
  wizard and reviewed onboarding, validated `setup plan` for installed and
  Docker MCP modes, exercised the installed CLI/MCP initialize and ping path,
  and cleaned its temporary vault and package-owned runtime. Separate isolated
  smokes installed and executed both the exact wheel and sdist.
- `release_check.py`, the version-only stable identity guard, CI guard and
  canonical publisher guard pass. The tag-bound `v2.1.0` identity check remains
  deliberately unavailable until the reviewed commit is tagged. The expected
  pre-PR warnings remain: the disposable demo index is intentionally absent, no
  PR URL is bound yet, and the checkout is not yet a committed Pages artifact.
- Exact scans `02ba69b2-fb72-4245-ba8a-80be51495a4c` and
  `4803d9c7-198a-4903-98de-22014dca58a9` first exposed the ambient root and
  sibling setup/onboarding provenance gaps. The completed fifth frozen scan
  `f9d74a4e-764c-423f-a3c9-5ba2e1d36152` then reported five findings on its old
  digest: PowerShell Unicode-quote injection, opaque documentation-shell
  parsing, mutable checkout markers, direct-entrypoint provenance and inline
  HTML event handlers. The current diff closes those shared boundaries:
  generated PowerShell argv escapes every recognized single-quote delimiter;
  ambient persistent flows require a regular vault manifest and reject source
  or nested checkout ambiguity without opening Git metadata; direct setup and
  onboarding require a deliberate root; and the documentation guard normalizes
  path/quote forms, fails closed on indirect shell execution and rejects `on*`
  attributes. Focused tests and fresh independent read-only slice reviews are
  clean. These remediations invalidate the fifth digest, so the complete staged
  diff still requires one final exact scan; its receipt belongs in the PR
  handoff to avoid a self-referential documentation change.
- Docker Desktop is not running in this Windows session, so a local container
  smoke was not repeated. The prior exact RC workflow passed Docker smoke; the
  stable PR must repeat it in GitHub CI before merge.

## Remaining Stable Gates

1. Record a final exact scan of the complete staged diff in the PR handoff; no
   reportable finding may remain.
2. Obtain a fresh independent read-only final review, push the branch, open the
   approve-ready PR, and require exact-head GitHub CI plus Pages validation.
3. Merge with the expected head SHA and require green `main` CI before creating
   annotated tag `v2.1.0`.
4. Exercise the `pypi` Trusted Publisher identity, install exact `2.1.0` from
   PyPI without cache, verify wizard/MCP/process cleanup, and confirm immutable
   GitHub Release assets, hashes, attestations and cumulative notes.

## Next Legal Product Work

After stable post-publication verification, batch `B04b` is the first legal
frontier: `BRG-003` and `BRG-017` may proceed as small, independently reviewed
changes. `BRG-019`, `MIG-001`, `GATE-B` and `ONB-001` remain dependency-gated.
