# Development Status

Updated: 2026-08-23

This is a concise public-repository handoff, not release evidence by itself.
The lead integrator updates it when a verified checkout, frontier, blocker, or
reproducible evidence changes.

## Canonical Baseline

- Public remote: `https://github.com/GonzaloTorreras/ai-dememory.git`
- Public `main` is a moving source branch. Resolve its current SHA before a
  handoff or merge with `git ls-remote origin refs/heads/main`; do not turn a
  historical release commit into a permanent `main` claim.
- Last externally verified public stable tag [`v2.1.1`](https://github.com/GonzaloTorreras/ai-dememory/releases/tag/v2.1.1):
  its annotated tag peels to
  `3dd65a18c5f26c5d03f24c5f3bb719769b581fa6`.
- [`ai-dememory 2.1.1`](https://pypi.org/project/ai-dememory/2.1.1/) is
  available from public PyPI as a non-yanked wheel and source distribution. The canonical
  [release workflow 32662792807](https://github.com/GonzaloTorreras/ai-dememory/actions/runs/32662792807)
  completed validation, provenance-attested build, protected PyPI publication,
  exact-version verification, and GitHub Release creation. Its public package
  route is the unpinned CLI install followed by `ai-dememory init
  ~/code/my-memory --wizard`; `--require-version` remains a legacy-compatible
  diagnostic option, not normal setup guidance.
- Historical prerelease evidence: [`v2.1.1rc2`](https://github.com/GonzaloTorreras/ai-dememory/releases/tag/v2.1.1rc2),
  an annotated tag whose peeled ref resolves to
  `ea7e1667c874a3cf2a8e1d87b916fb00172b71ce`. It is published on
  [TestPyPI](https://test.pypi.org/project/ai-dememory/2.1.1rc2/) through the
  successful canonical release
  [workflow 32647839323](https://github.com/GonzaloTorreras/ai-dememory/actions/runs/32647839323).
  It is release-candidate evidence, not an active installation route or a
  stable PyPI release.
- `v2.1.1rc1` remains historical prerelease evidence, not a second recommended
  installation route.
- Python 3.11+ remains the only headless runtime. Node is not an installation
  or background-process dependency.
- The former private checkout is historical input only. Private vaults,
  receipts, credentials, paths, and personal memory are not public source or
  release evidence.

The immutable release facts above were read back from the canonical public tag,
GitHub Release, release workflow, PyPI index, and artifact hashes. Current
`main` is source state rather than release evidence and must be read back
separately. This status file does not substitute for exact release checks.

## Current Maintenance Correction

The released `2.1.1` maintenance correction carries forward the two evaluated
increments without changing the V3 execution DAG. `2.1.1rc1` corrected an
unintended 2.1.0 compatibility contract; `2.1.1rc2` supplied the optional
local-API onboarding hint and documentation follow-up.

- Planning mapping: compatible maintenance remediation of completed `BRG-014`
  in `B04a`; it does not advance `B04b` or claim a V3 milestone.
- Problem: release preparation made `--require-version` look like a normal
  setup command and persisted an exact semver pin into generated MCP commands.
  A later patch package would then abort before MCP started.
- Resolution: new generated configuration, plans, plugin defaults, and Docker
  defaults omit the pin. Legacy configuration that still contains it is accepted
  as a no-op. `version-check` remains an explicit CI/support diagnostic.
- Release result: `v2.1.1` is now the public PyPI/GitHub stable release; its
  wheel and source hashes match the GitHub Release assets. `2.1.1rc1` and
  `2.1.1rc2` remain immutable TestPyPI evidence only, not active installation
  routes.
- Post-release first-run UX: `ai-dememory init ~/code/my-memory --wizard`
  after installing the exact stable package. Client configuration remains an
  optional, inspect-before-copy action.
- Optional API follow-up: after a completed operational wizard, the package may
  suggest the foreground loopback API command for a dashboard or script. It
  does not start, install, configure, or schedule the API.
- Preserved safeguards: explicit vault binding, `--require-bound-root`,
  server-enforced profiles/allowlists, preview/apply fingerprints, idle leases,
  and bounded resource policy.

## Current B04b Binding Increment

- PR [#27](https://github.com/GonzaloTorreras/ai-dememory/pull/27) was merged
  at `64622752d7d14c2a7f5bb49fc436010825d37d8c` after exact-head functional
  and security review found no actionable P0/P1/P2 issue and CI run
  [32589647682](https://github.com/GonzaloTorreras/ai-dememory/actions/runs/32589647682)
  passed all verification and cross-platform compatibility jobs.
- This first `BRG-003` increment rejects an explicitly supplied empty or
  whitespace-only `--root` before the CLI can fall through to
  `AI_DEMEMORY_ROOT` or CWD discovery. It covers global and post-command CLI
  binding plus direct MCP-config, setup, onboarding, and maintenance entry
  points; focused tests also preserve valid explicit-root precedence.
- PR [#29](https://github.com/GonzaloTorreras/ai-dememory/pull/29) was merged
  at `2d7212ad1205c58dd060b8048023fdb34c7ad164` after fresh exact-head
  functional/security review found no actionable P0/P1/P2 issue and CI run
  [32592493743](https://github.com/GonzaloTorreras/ai-dememory/actions/runs/32592493743)
  passed verification, all nine compatibility jobs, MCP runtime, install,
  package-build, and Docker smokes.
- This second `BRG-003` increment adds a pure runtime resolver and applies it
  to direct MCP runtime and `mcp-config`: `--stdio` and `--call` now require
  `--root` or `AI_DEMEMORY_ROOT`, while static `--list-tools` remains
  rootless. Packaged MCP dispatch no longer reaches CWD/package discovery,
  and generated client configurations remain compatible through explicit
  environment binding plus the legacy `--require-bound-root` flag.
- PR [#31](https://github.com/GonzaloTorreras/ai-dememory/pull/31) was merged
  at `e8a55506d95990e911edf7f3c1fa1570b87aed18` after a fresh independent
  exact-head review found no actionable P0/P1/P2 issue. CI run
  [32595063206](https://github.com/GonzaloTorreras/ai-dememory/actions/runs/32595063206)
  and Pages validation
  [32595063201](https://github.com/GonzaloTorreras/ai-dememory/actions/runs/32595063201)
  passed.
- This third `BRG-003` increment applies the same resolver to the direct
  local API and stateful hook surfaces. Those paths now require a nonempty
  absolute root from `--root` or `AI_DEMEMORY_ROOT` (with `~` expanded),
  reject duplicate/relative bindings, avoid opening an API socket before
  binding, and leave unbound hook dispatch as the documented `{}` no-op.
- PR [#33](https://github.com/GonzaloTorreras/ai-dememory/pull/33) was merged
  at `72d18eb271895e6fad7252e7b137ade33129644d` after a fresh exact-head
  functional/security review found no actionable P0/P1/P2 issue. CI run
  [32597614409](https://github.com/GonzaloTorreras/ai-dememory/actions/runs/32597614409)
  and Pages validation
  [32597614438](https://github.com/GonzaloTorreras/ai-dememory/actions/runs/32597614438)
  passed.
- This fourth `BRG-003` increment makes the `setup` and `onboard` execution
  paths select their vault only through the strict runtime resolver, before
  generic CLI CWD/package discovery. They reject blank and relative bindings,
  prefer an explicit absolute `--root` over the environment, and preserve
  `setup wizard` plus `init --wizard`, including both post-command root
  spellings. Packaged vault templates and active setup/maintenance guidance now
  show the same root-bound onboarding command.
- PR [#35](https://github.com/GonzaloTorreras/ai-dememory/pull/35) was merged
  at `e4f844413a874972d7626a325b47ec9dfa75a393` after a fresh independent
  exact-head review found no actionable P0/P1/P2 issue. CI run
  [32601078748](https://github.com/GonzaloTorreras/ai-dememory/actions/runs/32601078748)
  and Pages validation
  [32601078743](https://github.com/GonzaloTorreras/ai-dememory/actions/runs/32601078743)
  passed.
- This fifth `BRG-003` increment makes `maintenance run` select its vault
  through the strict runtime resolver before generic discovery, provider reads,
  lock acquisition, or supervised-child creation. It applies equally to real,
  dry-run, and supervised maintenance; absolute explicit `--root` takes
  precedence over the environment. `maintenance status` deliberately remains a
  compatible read-only legacy path. Source-checkout children use the trusted
  wrapper while installed packages retain the module entry point, both with an
  explicit root. PR #35 records full regression evidence of 856 passed and 53
  skipped, plus an exact working-tree security scan with zero findings.
- PR [#37](https://github.com/GonzaloTorreras/ai-dememory/pull/37) was merged
  at `4ff90b288c3d5ae9f522d5891fa5120f476ed781` after a fresh independent
  exact-head review found no actionable security issue. CI run
  [32606276539](https://github.com/GonzaloTorreras/ai-dememory/actions/runs/32606276539)
  and Pages validation passed.
- This sixth `BRG-003` increment makes stateful provider, import, and capture
  commands parse their own arguments before resolving a vault, then require an
  explicit runtime binding rather than generic CWD/package discovery.
  `providers detect` remains a deliberately rootless, read-only diagnostic.
  Documentation, generated setup guidance, and release checks now use the
  canonical root-bound command form. It is source hardening only: `BRG-003`
  remains `in_progress`, with no package, tag, release, vault, or V3-milestone
  change.
- PR [#39](https://github.com/GonzaloTorreras/ai-dememory/pull/39) was merged
  at `b585f913da8085231a1eb4d72671cd2e2f515869` after fresh independent
  exact-head review found no actionable P0/P1/P2/P3 issue. CI run
  [32611176677](https://github.com/GonzaloTorreras/ai-dememory/actions/runs/32611176677)
  passed 879 tests with 6 expected platform skips, and Pages validation
  [32611176739](https://github.com/GonzaloTorreras/ai-dememory/actions/runs/32611176739)
  passed.
- This seventh `BRG-003` increment binds configuration and review-state reads
  and writes to the selected vault root. It rejects external paths,
  symlinks/junctions, hard links, unstable file identity, descriptor
  substitution, non-regular input, oversized input, and invalid UTF-8.
  Onboarding reuses the validated configuration snapshot for planning and
  fingerprints, while the review API preserves direct `ValueError` contracts
  and the CLI returns controlled errors. The exact public-diff security review
  recorded complete coverage and zero reportable findings.
- It is source hardening only: it does not change a package, tag, release,
  vault, host configuration, or the V3 task state from `in_progress` to
  complete. The remaining strict-resolver inventory and any structural
  vault-validation policy stay within `BRG-003`.

## Verified Stable And Release-Candidate Evidence

- PR [#44](https://github.com/GonzaloTorreras/ai-dememory/pull/44) was merged
  at `3dd65a18c5f26c5d03f24c5f3bb719769b581fa6` after an independent exact-head
  review found no actionable P0/P1/P2 issue; its CI and Pages validation passed.
- The protected tag workflow
  [32662727498](https://github.com/GonzaloTorreras/ai-dememory/actions/runs/32662727498)
  created annotated `v2.1.1` and verified its peeled commit.
- The canonical stable release workflow
  [32662792807](https://github.com/GonzaloTorreras/ai-dememory/actions/runs/32662792807)
  passed validation, artifact build/checksums/attestation, protected PyPI
  publication, exact-index verification, and immutable GitHub Release creation.
- The public [v2.1.1 GitHub Release](https://github.com/GonzaloTorreras/ai-dememory/releases/tag/v2.1.1)
  includes the wheel, source distribution, release notes, and SHA256SUMS. PyPI
  readback confirmed both package files as non-yanked and their SHA-256 values
  match the release assets.

- PR [#42](https://github.com/GonzaloTorreras/ai-dememory/pull/42) was merged
  at `ea7e1667c874a3cf2a8e1d87b916fb00172b71ce` after release documentation
  truth was decoupled from the immutable package long description.
- The exact `main` CI run
  [32646728226](https://github.com/GonzaloTorreras/ai-dememory/actions/runs/32646728226)
  passed for `ea7e1667c874a3cf2a8e1d87b916fb00172b71ce`.
- The protected tag workflow
  [32647689405](https://github.com/GonzaloTorreras/ai-dememory/actions/runs/32647689405)
  created annotated `v2.1.1rc2` and verified its exact peeled commit.
- The canonical release workflow
  [32647839323](https://github.com/GonzaloTorreras/ai-dememory/actions/runs/32647839323)
  passed validation, artifact build/checksums/attestation, TestPyPI publication,
  exact-version index installation, and immutable GitHub prerelease creation.
- The immutable GitHub prerelease
  [v2.1.1rc2](https://github.com/GonzaloTorreras/ai-dememory/releases/tag/v2.1.1rc2)
  is published with wheel, source distribution, release notes, and SHA256SUMS.
- The following `rc1` evidence is retained as historical release record.
- PR [#21](https://github.com/GonzaloTorreras/ai-dememory/pull/21) was merged
  after a fresh independent exact-head compatibility/security review found no
  actionable P0/P1/P2 issue. Root binding, `--require-bound-root`,
  server-enforced profiles/allowlists, and idle leases remain intact.
- The exact `main` CI run
  [32531300657](https://github.com/GonzaloTorreras/ai-dememory/actions/runs/32531300657)
  passed for `a5140a81e4d153c8e7f41b0f2a88649030942c51`; its matching Pages
  and graph validation runs also passed.
- The source validation before merge passed: static documentation/site and
  Pages-artifact guards; 800 tests with 53 explicitly environment-conditioned
  skips; strict release checks; release identity guard; and an isolated package
  smoke covering wizard, MCP, hooks, maintenance, and public-only retrieval.
- The protected tag workflow
  [32557577347](https://github.com/GonzaloTorreras/ai-dememory/actions/runs/32557577347)
  created annotated `v2.1.1rc1` and verified that it resolves exactly to the
  approved green `main` commit.
- The canonical release workflow
  [32557614075](https://github.com/GonzaloTorreras/ai-dememory/actions/runs/32557614075)
  passed validation, artifact build/checksums/attestation, TestPyPI publication,
  and an exact-version install from the index. Direct TestPyPI readback reports
  `ai-dememory 2.1.1rc1` with Python requirement `>=3.11`.
- The immutable GitHub prerelease
  [v2.1.1rc1](https://github.com/GonzaloTorreras/ai-dememory/releases/tag/v2.1.1rc1)
  is published with wheel, source distribution, release notes, and SHA256SUMS.
- The RC2 workflow intentionally skipped stable PyPI publication. No Pages
  deployment, vault mutation, or host configuration write was performed by
  this maintenance correction.

## Resolved Historical Drift

The previous status snapshot still described an unfinished `2.1.0rc1` to stable
promotion, a release branch, and pre-tag gates. Those statements are historical
and no longer describe `origin/main`; they have been removed rather than carried
forward as an active checklist. The dated release record and historical ADRs
remain intact.

## Next Legal Action

1. Keep `2.1.1rc1` and `2.1.1rc2` as historical TestPyPI evidence; do not
   silently replace a package route with mutable source behavior or restore an
   active prerelease installation route.
2. Do not merge, tag, publish, deploy, or alter external configuration without
   the approval required by `AGENTS.md`.
3. Continue `BRG-003` with the remaining strict-resolver inventory and
   structural vault-validation policy. The root-bound configuration-reader and
   review-state boundary is covered for current entry points; provider/import/
   capture stateful actions are also covered. Preserve the intentional rootless
   read-only boundaries for
   `providers detect` and `maintenance status`. Keep scheduler and dual-path
   commands as separate compatibility slices. Do not claim structural vault
   validation merely from an absolute path. `BRG-017` follows within `B04b`;
   later tasks remain dependency-gated.
