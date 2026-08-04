# Solo-maintainer pull-request review

`ai-dememory` has one GitHub maintainer. Codex may implement and merge routine
repository changes under the owner's standing delegation, but every PR still
receives an independent technical review before merge.

The reviewer is a fresh read-only subagent, not another GitHub user. The root
agent publishes the result through `GonzaloTorreras`, the sole owner account.
GitHub approval reviews, email aliases, secondary accounts, bot approvals, and
writable synthetic status checks are not part of this model.

## Required sequence

1. Create a `codex/*` branch from current public `origin/main` and open a PR.
2. Run focused local checks and canonical `CI` for the exact PR base/head tuple.
3. Delegate one fresh read-only subagent to review that exact diff, CI evidence,
   security scope, and merge order. The reviewer must not mutate GitHub or Git.
4. Resolve every blocker and repeat CI/review after any new commit or base move.
5. Re-read the non-draft PR, its base and head SHAs, checks, changed files,
   unresolved threads, and clean worktree.
6. Publish this exact receipt from `GonzaloTorreras`:

   ```text
   <!-- codex-solo-review pr=<number> head=<head-sha> base=<base-sha> -->
   Verdict: READY
   Reviewer: <fresh-subagent-task>
   Scope: routine
   Evidence: <exact CI run URL and focused checks>
   ```

   Use `Scope: security-boundary` when the PR changes `AGENTS.md`,
   `scripts/ci_guard.py`, `.github/workflows/**`, `.github/actions/**`, this
   policy, or the policy ADR.
7. Re-read the tuple after posting. Merge through the GitHub API with
   `expected_head_sha`; never use an admin bypass or a stale receipt.
8. Verify the exact merged SHA and canonical `main` CI before continuing.

The comment is auditable owner-attested evidence. It is not a cryptographic
proof that a subagent ran. The sole owner account and the Codex execution
environment remain the trust root, so account security, immutable CI evidence,
and exact-SHA merge binding matter more than a simulated second identity.

## Live repository settings

Keep pull requests and strict canonical CI, but require no approving review and
no approval from a different last pusher:

```powershell
gh api --method PATCH `
  repos/GonzaloTorreras/ai-dememory/branches/main/protection/required_pull_request_reviews `
  -F dismiss_stale_reviews=true `
  -F require_code_owner_reviews=false `
  -F required_approving_review_count=0 `
  -F require_last_push_approval=false

gh api --method PATCH `
  repos/GonzaloTorreras/ai-dememory/branches/main/protection/required_status_checks `
  -F strict=true `
  -f 'contexts[]=verify'
```

Keep admins subject to protection and keep force-push and branch deletion
disabled. Read back the complete protection object after every change.

GitHub Actions no longer needs permission to approve pull requests:

```powershell
gh api --method PUT `
  repos/GonzaloTorreras/ai-dememory/actions/permissions/workflow `
  -f default_workflow_permissions=read `
  -F can_approve_pull_request_reviews=false
```

Do not make a `codex-review` commit status with the normal `GITHUB_TOKEN` a
required check. Every repository workflow shares the GitHub Actions app
identity, so another writable workflow could forge that context. Workflows must
not request `statuses: write`, `checks: write`, or `permissions: write-all`, and
no workflow other than `ci.yml` may define a job or job name equal to the
required `verify` context. Workflow YAML anchors, aliases, merge keys, explicit
tags, quoted mapping keys or permission scalars, escaped job names, and
block-scalar permission/name values are deliberately forbidden so this
dependency-free guard can fail closed without pretending to implement GitHub's
complete YAML resolver. Introducing a dedicated review app would add
credentials and operational cost without adding an independent human trust
domain.

## Authority boundaries

Standing delegation covers routine implementation, PR maintenance, comments,
exact-head merge, and post-merge verification. It does not cover package
publication, release-tag creation, trusted-publishing dispatch, secrets,
repository visibility, destructive recovery, or production deployment; those
remain explicit owner gates.

No email alias creates a distinct GitHub reviewer. A real secondary account
would add credentials and recovery risk while remaining controlled by the same
person, so it is deliberately excluded.

## Failure and rollback

Fail closed when the reviewer is not fresh, returns findings, the receipt is
missing, CI is stale or red, the base/head changes, threads remain open, or the
worktree is not clean.

Rollback preserves strict `verify`, admin enforcement, and force-push/deletion
prohibitions. Revert this policy through a new reviewed PR. Restore a formal
review requirement only after a genuinely independent collaborator or dedicated
review service exists and its identity, permissions, recovery, and bootstrap
path have been tested.
