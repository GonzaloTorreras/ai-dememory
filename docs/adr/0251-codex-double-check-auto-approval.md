# ADR 0251: Codex Double-Check Auto-Approval

## Status

Accepted.

## Context

The repository has one human owner and Codex performs routine implementation,
review coordination, merge and release work. Pull requests are currently
authored through the owner's account, and GitHub correctly refuses to let that
same account submit an approving review. Requiring another human account would
contradict the AI-operated repository model without adding a meaningful
technical check.

GitHub Actions can submit pull-request reviews using its separate bot identity,
but enabling that capability is explicitly security-sensitive. A workflow with
write permission must not execute or checkout untrusted PR code.

## Decision

Use a trusted default-branch `issue_comment` workflow to submit the formal
approval after the real double-check:

- canonical CI must have succeeded for the exact current PR number, head SHA,
  and base SHA;
- a fresh read-only subagent must approve that exact tuple and diff;
- Codex posts a machine-readable tuple-bound receipt from the owner account;
- the PR must be internal, non-draft, owner-authored, `codex/*`, and target
  `main`;
- the privileged workflow re-reads all state immediately before approving;
- PRs modifying the trusted workflows, local actions, review policy, or CI
  drift guard are excluded and use an explicit bootstrap procedure; incomplete
  or over-limit changed-file listings fail closed;
- the workflow never checks out code, restores caches, downloads artifacts or
  evaluates untrusted PR content as shell code.

Keep default workflow permissions read-only. Enable only
`can_approve_pull_request_reviews` after this workflow exists on `main`.
Branch protection then requires one approval, dismisses stale reviews, requires
approval after the latest push, and uses strict required CI.

## Consequences

- GitHub displays a formal approval from `github-actions[bot]` even though the
  repository has only one human owner.
- The approval is auditable and bound to the reviewed commit instead of a
  reusable label or branch name.
- New commits or base movement invalidate old receipts.
- Human interaction is removed from routine approval without removing CI,
  independent review or protected-branch gates.

## Limitations

- The first rollout PR cannot approve itself because the workflow must already
  exist on the default branch.
- The subagent name and evidence in the receipt are owner-attested policy data;
  GitHub does not cryptographically authenticate a subagent identity.
- Codex still has to post the receipt after the fresh review; raw CI success is
  intentionally insufficient.
- Compromise of the sole owner account remains a repository-level risk and is
  handled by GitHub account security and break-glass recovery, not this flow.

## Future Risks

- Broadening accepted authors, branches or repositories could turn the workflow
  into a privilege-escalation path.
- Adding checkout, cache restore, artifact execution or PR-derived shell
  interpolation would invalidate the security model.
- The CI guard is drift detection, not a malicious-change sandbox; trusted
  boundary changes still require the explicit bootstrap review.
- GitHub permission semantics may change and require guard/readback updates.

## Dependencies

- ADR 0019 defines executable CI workflow drift checks.
- ADR 0247 defines AI-operated tag releases.
- `AGENTS.md` defines the fresh read-only subagent double-check.
- `.github/workflows/ci.yml` is the canonical required validation workflow.
