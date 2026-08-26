# Development Status

Updated: 2026-08-26

This is a concise public-repository handoff, not release evidence by itself.
The lead integrator updates it when a verified checkout, frontier, blocker, or
reproducible evidence changes.

## Canonical Baseline

- Public remote: `https://github.com/GonzaloTorreras/ai-dememory.git`
- Public `main` is a moving source branch. Resolve its current SHA before a
  handoff or merge with `git ls-remote origin refs/heads/main`; do not turn a
  historical release commit into a permanent `main` claim.
- For this handoff, public `main` was read back at
  `02aa9945f82fc895eeb4420a932610a130a497b2`, the squash merge result of
  [PR #50](https://github.com/GonzaloTorreras/ai-dememory/pull/50). Its history
  contains the strict maintenance and scheduler corrections from PRs #50 and
  #48, the planning-authority consolidation from PR #49, the planning-only
  governed-learning handoff from PR #47, and the unpublished `2.1.2`
  default-vault/wizard correction from PR #46.
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
  precedence over the environment. At that point `maintenance status` remained
  a compatible read-only legacy path; the ninth increment below closes that
  temporary exception. Source-checkout children use the trusted wrapper while
  installed packages retain the module entry point, both with an explicit root.
  PR #35 records full regression evidence of 856 passed and 53 skipped, plus an
  exact working-tree security scan with zero findings.
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
- PR [#48](https://github.com/GonzaloTorreras/ai-dememory/pull/48) was squash
  merged at `bf611ac2e2ebf819adb74f79e6d6ef093c0503d0` after all ten CI jobs and
  Pages validation passed. Its exact committed diff was sealed as canonical
  security scan `46e5e575_dcca4a96_20260825T205252Z`; the post-seal validator
  returned `status: valid` with complete coverage, zero deferred work, zero
  candidates, and zero findings. A fresh GitHub-context review returned no
  blockers and explicitly recommended the exact-head squash merge.
- This eighth `BRG-003` increment makes the complete `schedule` command
  family parse its own grammar before any vault lookup. `schedule doctor`
  remains a genuinely rootless environment check; `plan`, `cron`, `setup`,
  `install`, `status`, and `remove`, including their dry-run forms, resolve only
  through `--root`, `AI_DEMEMORY_ROOT`, or the saved local default. None can
  fall through to CWD/package discovery. This also reflects that a real
  `schedule status` may refresh or clear verification evidence and therefore
  is not merely a static command. The scheduler-plan smoke now rejects missing,
  duplicated, misplaced, or incorrect root bindings and distinguishes the host
  vault from the Docker runtime root. Its installed and Docker previews must
  match the exact platform-specific host command set, complete maintenance
  argv, root-derived task namespace, safety flags, fingerprint-bound apply
  argv, independently recomputed plan fingerprint, and canonical cron entries;
  a malformed duplicate or internally consistent forged plan cannot hide
  behind valid-looking metadata.
- The scheduler increment remains source hardening with `BRG-003` still
  `in_progress`. It does not change scheduler definitions, an installed vault,
  package metadata, a tag, a release, or the current V3 frontier.
- Local evidence for this checkout: the complete unit suite passed 935 tests
  with 59 expected platform skips; the integrated memory-tools module passed
  580 tests with 45 expected skips; the documentation/planning guards passed;
  and a fresh venv install smoke installed the local package and exercised its
  console script, exact installed and Docker scheduler-plan validation, MCP,
  API, hooks, providers, and maintenance successfully. The Docker step was a
  plan-only preview: the smoke removed its temporary environment and neither
  ran Docker nor installed host scheduler definitions.
- PR [#49](https://github.com/GonzaloTorreras/ai-dememory/pull/49) was squash
  merged at `2c3e80735b4412d94c8a67983a5d410b417fb5e9`. Its exact head passed CI
  run [32902951391](https://github.com/GonzaloTorreras/ai-dememory/actions/runs/32902951391)
  and Pages run
  [32902951388](https://github.com/GonzaloTorreras/ai-dememory/actions/runs/32902951388),
  plus fresh independent normative and security reviews. It consolidated the
  planning authority and hardened the advisory release-checklist parser; it did
  not change the V3 frontier or publish a package.
- PR [#50](https://github.com/GonzaloTorreras/ai-dememory/pull/50) was squash
  merged at `02aa9945f82fc895eeb4420a932610a130a497b2`. Its exact head passed CI
  run [32905559559](https://github.com/GonzaloTorreras/ai-dememory/actions/runs/32905559559)
  and Pages run
  [32905559592](https://github.com/GonzaloTorreras/ai-dememory/actions/runs/32905559592),
  plus fresh functional and sealed security reviews with zero findings. The
  resulting public-main push CI run
  [32907288634](https://github.com/GonzaloTorreras/ai-dememory/actions/runs/32907288634)
  also passed verification and all nine OS/Python compatibility jobs.
- The merged ninth `BRG-003` increment routes the complete `maintenance`
  family through its own parser. Both `run` and read-only `status` now resolve
  only `--root`, `AI_DEMEMORY_ROOT`, or the saved local default, in that order,
  and never discover a vault from CWD or the source checkout. Invalid grammar,
  abbreviations, duplicate, blank, relative, or misplaced roots fail before
  configuration reads, status work, locks, providers, or child processes.
  Rootless help remains available and `status` preserves its JSON contract and
  makes no vault writes.
- Local evidence for this increment: all 25 maintenance-focused tests passed;
  the runtime-binding help test passed; and the integrated memory-tools module
  passed 589 tests with 45 expected platform skips. Thirteen install-smoke
  regressions also passed, and a fresh venv installed the local package and
  proved that installed `maintenance status` rejects an unbound foreign CWD,
  then uses the saved vault from that same deliberately poisoned directory;
  the rest of the installed CLI, API, MCP, hook, provider, scheduler, and recall
  smoke remained green. This remains compatible source hardening: `BRG-003`
  stays `in_progress`, and no version, task state, package, tag, vault,
  scheduler definition, or release changes.

## Completed BRG-017 Strict Configuration Boundary

This checkout completes `BRG-017` within batch `B04b`; its independent review,
PR, merge, and public-main CI remain delivery evidence rather than a reason to
broaden the implementation.

- Main vault configuration and the separate generated review-state file now
  use Python 3.11 `tomllib` with closed, versioned structural allowlists. Empty
  and partial configuration remains valid, while malformed TOML, duplicate
  definitions, unknown sections/providers/keys, nested surprises, wrong types,
  boolean-as-integer values, non-string arrays, non-finite numbers, unsafe
  review identifiers, invalid UTF-8, and oversized files fail closed.
- Configuration writers validate the existing snapshot, requested update, and
  complete rendered candidate before their atomic write. Invalid input cannot
  create parent directories or partially rewrite a file, and equivalent
  noncanonical table spellings are rejected rather than duplicated.
- Onboarding, setup health, doctor, providers, maintenance, scheduling, sleep,
  review operations, and resource policy share controlled error boundaries.
  Diagnostics retain stable codes and allowlisted field names but never echo
  unknown keys, values, custom review-state/provider paths, OS error text, or
  chained causes. Successful local administrative status and plan projections
  retain their existing paths and payloads.
- Exact-head review closed two boundary gaps before merge: onboarding now
  rejects a generated configuration candidate that exceeds the same 64 KiB
  limit before creating an apply plan, and invalid recall configuration makes
  hooks inert even when the vault already has an index. Retrieval or injection
  can no longer be re-enabled by falling back from an invalid explicit opt-out.
- The same validation run reproduced an intermittent Windows loopback reset on
  rejected POST requests. The API now authenticates the request context and
  optional key first, consumes only the already bounded request body, and then
  enforces mutation intent and JSON type. Stress coverage observed no aborted
  connections or residual server threads; the origin, intent, content-type,
  64 KiB body, and 15-second timeout controls remain unchanged.
- The operator guide is `docs/configuration.md`; ADR 0262 records why strict
  parsing is implemented in the existing Python runtime without a second
  parser, daemon, database, model call, or Node dependency.
- Rebased exact-head evidence on public `main` ran 999 tests in the complete
  suite with 59 expected platform skips. A focused API, onboarding, hook, and
  turn-context regression set ran 99 tests. Python compilation, diff
  validation, the planning contract, and a repository secret scan with zero
  findings also passed.
  A fresh virtual environment installed the local package and exercised the
  installed CLI, strict config consumers, API, MCP, hooks, providers,
  maintenance, and scheduler successfully; the isolated package-build smoke
  built both distributions and passed `twine check` on this exact head.
  Exact-head independent review and PR CI are still required before merge.
- The normative DAG now marks `BRG-017` complete with explicit evidence paths.
  `BRG-003` is the sole current frontier; `BRG-019` remains pending on that
  task, and no package, tag, release, installed vault, host integration, or
  future learning capability changes in this increment.

## Merged 2.1.2 Source Candidate (Unpublished)

This compatible `BRG-003` / `B04b` correction was merged from
`codex/default-vault-wizard-ux` by PR #46. It is present on public `main` at
`df8fca0e00e5b060e21fbde6bb1cb338c05c75fc` and does not advance the V3 DAG.

- A user may explicitly select one initialized local vault with
  `ai-dememory vault use <absolute-vault-path>`. Runtime resolution is now
  `--root`, then `AI_DEMEMORY_ROOT`, then that saved selector. The selector is
  local-only, validates the selected vault configuration, and fails closed for
  stale, malformed, linked, or unsafe state. It does not restore CWD or source
  checkout discovery for strict API, MCP, hook, setup, provider, import, or
  capture paths. `vault current` and `vault clear` are the inspection and
  recovery operations.
- The operational setup wizard now explains its limited scope, intensity
  ceilings, host-AI policy, schedule boundary, and review-first Stop proposals.
  It keeps durable personal onboarding separate and offers the local selector
  only after a successful apply with an explicit `[y/N]` decision.
- A test-only portability follow-up verifies the canonical selected path rather
  than a platform alias of the temporary directory. This preserves the intended
  runtime behavior on macOS `/var` and Windows short-path aliases.
- Source metadata and public documentation call this `2.1.2` an unreleased
  candidate. Stable `2.1.1` remains the only published PyPI/GitHub install
  route until a new tag, package publication, and external readback complete.
- Local evidence recorded by PR #46:
  `python -B -m unittest discover -s tests -t .` completed with 929 passing
  tests and 59 expected skips; the documentation guard, static Pages validation
  tests, targeted MCP checks, visual QA, and a fresh security review passed.
  Exact-head CI run
  [32709293400](https://github.com/GonzaloTorreras/ai-dememory/actions/runs/32709293400)
  and Pages validation
  [32709293326](https://github.com/GonzaloTorreras/ai-dememory/actions/runs/32709293326)
  both passed for `60979bbcb4f8ffa9b62c054f7babff2c210a7c20` before the squash merge.
  No tag, TestPyPI/PyPI publication, or `2.1.2` GitHub Release followed.

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

1. Keep source `2.1.2` explicitly unpublished until the remaining
   release-relevant `B04b` work is cut into a reviewed `2.1.2rc1`, installed
   from TestPyPI, and read back. Each tag and publication must remain bound to
   its exact commit/tag tuple, artifact, workflow, and package-index evidence.
2. Continue the sole `BRG-003` frontier by making rootless `providers detect`
   independent of vault selectors and configuration reads, then resume the
   remaining strict-resolver inventory and structural vault-validation policy.
   The root-bound configuration-reader, review-state,
   provider/import/capture, scheduler, and maintenance boundaries are covered
   for their current entry points. Do not claim structural vault validation
   merely from an absolute path: explicit and environment bindings still
   require shared real-directory, configuration, link-chain, and
   stable-identity checks planned inside `BRG-003`.
3. Preserve completed `BRG-017`, then deliver `BRG-019`, `MIG-001`, and the
   externally read-back `GATE-B` in their normative order after `BRG-003`.
4. Keep `OBS-001`, `OUT-001`, `CON-001`, and `MEM-001` as future work. Their
   [governed learning handoff](governed-learning-loop-handoff.md) adds no
   current runtime, config, wizard, ranking, or canonical-write capability.
5. Keep `2.1.1rc1` and `2.1.1rc2` as historical TestPyPI evidence. The next
   release identity remains `2.1.2rc1` and then `2.1.2`; do not skip directly
   to `2.1.3`, reuse a tag, or treat source metadata as publication evidence.
