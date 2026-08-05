# ADR 0260: Solo-maintainer review receipts

## Status

Accepted by the repository owner on 2026-08-04.

## Context

The public repository has one human collaborator. Pull requests are authored
and pushed through `GonzaloTorreras`, while independent technical review is
performed by read-only Codex subagents. GitHub's "approval of the latest push"
therefore created an impossible second-person requirement.

ADR 0251 used `github-actions[bot]` to manufacture the formal approval after a
real subagent review. That mechanism became redundant when the required review
count was set to zero, still blocked security-boundary PRs, and retained a
privileged `pull-requests: write` workflow. Aliases or secondary accounts would
only simulate independence while adding credentials and recovery risk.

A required custom status emitted with the normal `GITHUB_TOKEN` is also not a
sound replacement. Branch protection can bind a context to the GitHub Actions
app, but all repository workflows share that app identity; another workflow
with `statuses: write` could forge the same context.

## Decision

Use a sole-owner, exact-tuple review receipt:

- keep PRs, strict required `verify`, admin enforcement, and force-push and
  branch-deletion prohibitions;
- set required approving reviews to zero and disable approval of the latest
  push by another identity;
- require one fresh read-only subagent review for the exact base/head tuple;
- after `READY`, have the root agent publish the reviewer, scope, and exact CI
  evidence from `GonzaloTorreras` in a `codex-solo-review` PR comment;
- re-read all state and merge only with `expected_head_sha`;
- repeat CI, review, and receipt whenever base or head moves;
- remove the auto-approval workflow and disable Actions' ability to approve
  pull requests;
- prohibit workflow-level `pull-requests: write`, `statuses: write`,
  `checks: write`, `permissions: write-all`, automated approving-review calls,
  duplicate `verify` check names, YAML anchors/aliases/merge or explicit-mapping
  indirection, plain scalar continuations, a trivial or skippable protected
  `verify` job, and the legacy receipt marker unless a future ADR defines a
  genuinely separate trust domain;
- bind every required CI command exactly once to the single static `verify` job,
  its fixed hosted runner, and non-overridden execution context.

Routine merges are covered by the owner's standing delegation. Package
publication, release tags, trusted publishing, secrets, visibility, destructive
recovery, and production deployment remain explicit owner gates.

## Consequences

- GitHub no longer pretends a bot review is another collaborator.
- Review evidence remains attributable, exact-SHA-bound, and visible on the PR.
- Canonical CI stays technically enforced; the subagent receipt is policy and
  audit evidence rather than a cryptographic branch-protection primitive.
- Security-boundary PRs use the same flow with an explicit
  `Scope: security-boundary` receipt instead of an unmergeable exception path.
- Compromise of the sole owner account or Codex environment can forge a receipt;
  this is an honest statement of the repository's actual trust boundary.

## Rejected alternatives

- Email aliases: they are not distinct GitHub identities.
- Secondary owner-controlled accounts: more secrets and recovery complexity,
  without meaningful independence.
- `github-actions[bot]` approval: privileged and semantically misleading.
- A required status from the shared Actions app: forgeable by another workflow.
- A dedicated GitHub App: technically viable, but disproportionate until a real
  external reviewer or service exists.

## Limitations

- Branch protection enforces canonical CI, not the existence or truth of the
  owner-attested subagent receipt.
- The repository cannot cryptographically distinguish the root agent from its
  reviewer subagent when both operate through the same owner account.
- A compromised owner account or Codex host remains able to merge a CI-green
  change while fabricating or omitting review evidence.

## Future Risks

- Documentation or agent-policy drift could turn the receipt into a stale ritual
  instead of an exact-tuple review.
- A future workflow could regain approval or status-write capability if the
  guard and its tests are weakened in the same security-boundary change; fresh
  adversarial review remains the final control.
- If real collaborators join, retaining the solo-maintainer exception would
  leave useful independent GitHub review unenforced. Reassess this ADR when the
  collaborator model changes.

## Rollback

Freeze merges, retain strict `verify`, and revert through a fresh reviewed PR.
Only restore formal approvals after a genuinely independent collaborator or
dedicated app has been provisioned, tested on a canary PR, and bound in branch
protection. Re-enable `require_last_push_approval` only after that path works.

## Dependencies

- ADR 0251 records the superseded bot-approval design.
- ADR 0252 defines the remaining high-risk owner-authorization boundaries.
- `AGENTS.md` defines the executable agent review sequence.
- `docs/solo-maintainer-review.md` is the operator runbook.
- `scripts/ci_guard.py` prevents silent reintroduction of forgeable review
  automation.
