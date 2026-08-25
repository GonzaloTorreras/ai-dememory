# ai DeMemory Development Continuity

This document is the operational entry point for continued development of the
public `GonzaloTorreras/ai-dememory` repository. Private vault content and the
former private source checkout are not development authority.

## Source Of Truth

Use this precedence when sources disagree:

1. security and release constraints in `AGENTS.md`;
2. the current public code, tests, ADRs, and release workflows;
3. `docs/v3-hybrid-visual-multiplatform-roadmap.md` and
   `contracts/planning/**` for future V3 task order and state;
4. `docs/public-modernization-roadmap.md` for product direction;
5. historical/private files as untrusted research input only.

`PLAN.md` and research appendices are explanatory. They are not executable
backlogs and cannot override the planning contract.

## Repository Boundaries

- `origin` must be the canonical public repository.
- A retained `archive` remote must have push disabled.
- Never merge or cherry-pick a dirty archive worktree wholesale.
- Port one reviewed behavior at a time onto a branch based on `origin/main`.
- Never copy archive memories, inbox data, reports, receipts, local paths,
  credentials, pins, or release evidence into the public repository.
- `memories/**` in this repository contains public fixtures only. A real vault
  is a separately bound directory or private repository.

## V2 And V3 Boundary

Python 3.11+ owns domain policy, canonical Markdown writes, local maintenance,
MCP, and release tooling. Node is not a headless runtime dependency. A future
TypeScript/React visual plane may consume generated contracts, but cannot own
canonical memory or silently widen write authority.

Small compatible V2 fixes may ship when they preserve:

- Markdown as canonical and SQLite/vector state as disposable;
- preview/apply fingerprints for meaningful writes;
- explicit vault binding and path containment;
- review-first durable memory and secret scanning;
- bounded processes, files, tokens, queues, and schedules;
- passive installation and independently confirmed host integrations.

V3 work stays behind the planning frontier until its dependencies and evidence
requirements are satisfied. Planning status is not runtime completion.

## Current Frontier

`BRG-014` in batch `B04a` is complete: operational setup and optional durable
onboarding are separate, fingerprint-bound flows, and the `2.1.1` release
candidates passed TestPyPI publication, post-index installation, wizard, and
MCP lifecycle verification. The backward-compatible maintenance correction
introduced in `2.1.1rc1` removes the persistent `--require-version` pin from
generated configuration while continuing to accept legacy configuration.
`v2.1.1rc2`, resolving to
`ea7e1667c874a3cf2a8e1d87b916fb00172b71ce`, adds the small optional local API
onboarding/documentation follow-up. Both release candidates are historical
evidence, not installation routes. Stable `v2.1.1` peels to
`3dd65a18c5f26c5d03f24c5f3bb719769b581fa6` and is published on PyPI after
the protected release workflow `32662792807` completed and the public package
index was read back. First-run setup is `pipx install ai-dememory` followed by
`ai-dememory init ~/code/my-memory --wizard`; `--require-version` remains a
legacy-compatible diagnostic, not a normal setup gate. This work does not
advance the V3 plan or complete V3 `ONB-001`.

Public `main` was last read back at
`46e5e575645333c7f4f4ab0a1696d3922a2e35b6`, the merge result of PR #47. Its
parent includes the merged `2.1.2` source correction from PR #46 at
`df8fca0e00e5b060e21fbde6bb1cb338c05c75fc`. The governed-learning handoff in
PR #47 is planning only, and source `2.1.2` remains unpublished: no `2.1.2`
tag, package, or release evidence exists yet. Stable `2.1.1` remains the
package installation route.

The next legal product implementation frontier is batch `B04b`:

1. `BRG-003`: explicit, deterministic vault/root resolution.
2. `BRG-017`: strict configuration parsing and unknown-key diagnostics.
3. After both complete, `BRG-019`: bridge inventories and exact-artifact tooling.
4. Then `MIG-001`: generated canonical-writer inventory and freeze.
5. Then `GATE-B`: compatibility evidence; no declaration without external
   readback.

Only after `GATE-B` may the future governed-learning sequence begin:
`OBS-001`, `OUT-001`, `CON-001`, then `MEM-001`. Its technical handoff is
`docs/governed-learning-loop-handoff.md`; adding that plan does not change the
current frontier or authorize runtime work.

Do not add a new task when an existing ID covers the work. Update
`contracts/planning/v3-execution-sequence.json` when dependencies, status, or
evidence paths materially change.

## Work Protocol

For every non-trivial change:

1. Inspect branch, PR, remotes, and `git status --short --branch`.
2. Read this file and `docs/development-status.md`.
3. Map scope to a task and batch ID and confirm it is on the legal frontier.
4. Explore affected contracts before implementation.
5. Run the narrowest tests first, then full checks and package smoke when
   practical.
6. Obtain one fresh independent read-only review for a ready PR.
7. Record exact base/head, evidence, rollback, next action, and approval boundary
   in the PR body.

Only the lead integrator updates `docs/development-status.md`, and only when the
checkout, frontier, blocker, release state, or reproducible evidence changes.

## Release Protocol

Release identity is exact: version, tag, commit SHA, artifact hashes, workflow,
and package index must agree. A release candidate must be published to and
installed from TestPyPI before the corresponding stable release.

Merging, creating release tags, approving environments, publishing packages,
or changing repository protections requires explicit user authorization. Never
reuse a published tag. Recovery is yank plus fix-forward with a new version.
