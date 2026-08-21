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

This branch corrects an unintended 2.1.0 compatibility contract without
changing the V3 execution DAG.

- Planning mapping: compatible maintenance remediation of completed `BRG-014`
  in `B04a`; it does not advance `B04b` or claim a V3 milestone.
- Problem: release preparation made `--require-version` look like a normal
  setup command and persisted an exact semver pin into generated MCP commands.
  A later patch package would then abort before MCP started.
- Resolution: new generated configuration, plans, plugin defaults, and Docker
  defaults omit the pin. Legacy configuration that still contains it is accepted
  as a no-op. `version-check` remains an explicit CI/support diagnostic.
- Release coupling: the behavioral correction and wizard-first documentation
  must ship together as a new patch release. Do not merge the documentation as
  a standalone change while the published 2.1.0 package still requires the old
  init-wizard flag.
- First-run UX: `pipx install ai-dememory==2.1.0` followed by
  `ai-dememory init ~/code/my-memory --wizard`. Client configuration remains an
  optional, inspect-before-copy action.
- Preserved safeguards: explicit vault binding, `--require-bound-root`,
  server-enforced profiles/allowlists, preview/apply fingerprints, idle leases,
  and bounded resource policy.

## Evidence So Far

- Static documentation/site guard and the Pages artifact guard pass against the
  current worktree.
- `python -m unittest discover -s tests` passes: 798 tests, 53 explicitly
  environment-conditioned skips. The suite's intentional negative `--guided`
  parser case writes an argparse error while still passing its assertion.
- Fresh independent compatibility and security reviews found no source-security
  or legacy-configuration blocker. They confirmed root binding,
  `--require-bound-root`, server-enforced profiles/allowlists, and idle leases
  remain intact.
- The independent reviewer records one hard release gate: this branch is not
  mergeable as documentation-only work because its user instructions describe
  behavior absent from published 2.1.0. The correction must become the next
  package patch and its install references must match that released identity.
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
   in draft until its patch-release coupling is complete.
2. Before any merge, prepare the next patch release identity, update every
   stable install reference to that identity, and repeat the release evidence
   for the exact candidate.
3. Do not merge, tag, publish, deploy, or alter external configuration without
   the approval required by `AGENTS.md`.
4. After this small V2 correction, the next product frontier remains `B04b`:
   `BRG-003` (deterministic vault/root binding) and `BRG-017` (strict config
   parsing). `BRG-019`, `MIG-001`, `GATE-B`, and `ONB-001` remain gated by their
   declared dependencies and evidence.
