# Development Status

Updated: 2026-08-21

This is a concise public-repository handoff, not release evidence by itself.
The lead integrator updates it when a verified checkout, frontier, blocker, or
reproducible evidence changes.

## Canonical Baseline

- Public remote: `https://github.com/GonzaloTorreras/ai-dememory.git`
- Public `main` and annotated tag `v2.1.0`:
  `f43e55d824e7b085b5a7f8518e6dad9d5ddaef99`
- Current published release line in user documentation: `2.1.0`
- Current source-only patch candidate: `2.1.1rc1`. It is neither tagged nor
  published; its package-index evidence must be collected independently.
- Python 3.11+ remains the only headless runtime. Node is not an installation
  or background-process dependency.
- The former private checkout is historical input only. Private vaults,
  receipts, credentials, paths, and personal memory are not public source or
  release evidence.

The exact tagged baseline was verified locally from the canonical `origin/main`
remote. A future release must still perform its own external package-index,
GitHub-release, CI, and Pages readback; this file does not substitute for those
checks.

## Current Maintenance Correction

This branch prepares a 2.1.1 release candidate that corrects an unintended
2.1.0 compatibility contract without changing the V3 execution DAG.

- Planning mapping: compatible maintenance remediation of completed `BRG-014`
  in `B04a`; it does not advance `B04b` or claim a V3 milestone.
- Problem: release preparation made `--require-version` look like a normal
  setup command and persisted an exact semver pin into generated MCP commands.
  A later patch package would then abort before MCP started.
- Resolution: new generated configuration, plans, plugin defaults, and Docker
  defaults omit the pin. Legacy configuration that still contains it is accepted
  as a no-op. `version-check` remains an explicit CI/support diagnostic.
- Release coupling: `2.1.0` remains the published stable package and retains
  its historical explicit wizard version flag. The new wizard-first command is
  scoped to source candidate `2.1.1rc1`; it cannot be presented as an
  installable PyPI path until the exact candidate is tagged and published.
  The documentation and static site must show those two release lenses
  separately.
- Candidate first-run UX: `ai-dememory init ~/code/my-memory --wizard` after
  installing the future 2.1.1 release artifact. Client configuration remains
  an optional, inspect-before-copy action.
- Preserved safeguards: explicit vault binding, `--require-bound-root`,
  server-enforced profiles/allowlists, preview/apply fingerprints, idle leases,
  and bounded resource policy.

## Evidence So Far

- Static documentation/site guard and the Pages artifact guard pass against the
  current worktree.
- `python -m unittest discover -s tests` passes: 800 tests, 53 explicitly
  environment-conditioned skips. The suite's intentional negative `--guided`
  parser case writes an argparse error while still passing its assertion.
- `ai_release_guard.py --tag v2.1.1rc1 --version-only`, strict release checks,
  and an isolated `install_smoke.py --package .` pass for the exact candidate.
  The smoke exercises the installed package, wizard, MCP, hook, maintenance,
  and public-only retrieval paths without publishing an artifact.
- Fresh independent compatibility and security reviews found no source-security
  or legacy-configuration blocker. They confirmed root binding,
  `--require-bound-root`, server-enforced profiles/allowlists, and idle leases
  remain intact.
- The independent reviewer records one hard release gate: this branch is not
  mergeable as documentation-only work because its user instructions describe
  behavior absent from published 2.1.0. The correction must become the next
  package patch. It is now versioned as `2.1.1rc1`, but its exact source,
  package, documentation and install evidence must still be rerun together.
- The review was a scoped manual read-only diff review; no sealed external
  security-scan artifact was produced for this maintenance correction.
- Draft PR [#21](https://github.com/GonzaloTorreras/ai-dememory/pull/21)
  records the exact branch/base, evidence, rollback, and hard merge gate.
- No package, tag, GitHub Release, PyPI publication, Pages deployment, vault
  mutation, or host configuration write is part of this maintenance correction.

## Resolved Historical Drift

The previous status snapshot still described an unfinished `2.1.0rc1` to stable
promotion, a release branch, and pre-tag gates. Those statements are historical
and no longer describe `origin/main`; they have been removed rather than carried
forward as an active checklist. The dated release record and historical ADRs
remain intact.

## Next Legal Action

1. Keep draft PR [#21](https://github.com/GonzaloTorreras/ai-dememory/pull/21)
   in draft while the `2.1.1rc1` source/package/documentation contract is
   validated and independently reviewed.
2. Keep 2.1.0 stable instructions and `2.1.1rc1` candidate instructions
   distinct. Do not change public stable install references to 2.1.1 until the
   RC has been tagged, published to TestPyPI, and passed its exact-index
   installation evidence.
3. After a green exact-head PR and fresh review, obtain explicit approval
   before merging. A later exact-tag authorization and a separate publication
   authorization remain required for the candidate.
4. Do not merge, tag, publish, deploy, or alter external configuration without
   the approval required by `AGENTS.md`.
5. After this small V2 correction, the next product frontier remains `B04b`:
   `BRG-003` (deterministic vault/root binding) and `BRG-017` (strict config
   parsing). `BRG-019`, `MIG-001`, `GATE-B`, and `ONB-001` remain gated by their
   declared dependencies and evidence.
