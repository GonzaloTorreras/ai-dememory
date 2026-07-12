# Codex double-check auto-approval

`ai-dememory` is operated by Codex through Gonzalo's sole-owner GitHub account.
GitHub does not allow that account to approve a pull request it authored, so a
trusted default-branch workflow records the formal approval as
`github-actions[bot]` after Codex completes the real technical double-check.

## Required sequence

1. Codex pushes a `codex/*` branch and opens a non-draft PR to `main`.
2. The branch is current with `main`, and canonical `CI` succeeds for the exact
   PR number, head SHA, and base SHA.
3. A fresh read-only subagent reviews that exact tuple and diff with GitHub
   context and returns `APPROVED` without mutating repository state.
4. Codex verifies the tuple is unchanged and posts this receipt from the
   trusted `GonzaloTorreras` account:

   ```text
   <!-- codex-double-check pr=<number> head=<40-character-head-sha> base=<40-character-base-sha> -->
   Verdict: APPROVED
   Reviewer: <fresh-review-task>
   Evidence: <CI run URL and focused local checks>
   ```

5. `.github/workflows/auto-approve.yml`, loaded from the default branch,
   re-reads the PR and latest canonical CI run. It approves only when author,
   repository, branch, PR number, base SHA, head SHA, draft state, receipt and
   CI association all match.
6. Codex rechecks mergeability and required checks, then merges according to
   the repository's AI-operated release policy.

Any new head commit or movement of `main` makes the tuple stale. Codex must
bring the branch current and repeat CI, review and receipt generation. The
workflow also refuses PRs that change its security boundary: `AGENTS.md`,
`scripts/ci_guard.py`, `.github/workflows/*`, or `.github/actions/*`.
It compares the paginated file-list count with GitHub's PR metadata and fails
closed if the list is truncated or the PR exceeds GitHub's 3,000-file limit.

The receipt is an owner-attested policy signal: GitHub verifies who posted it,
while the repository workflow trusts the stated reviewer and evidence. The
fresh subagent review is enforced by Codex policy and audit history, not by a
cryptographic subagent identity.

## Repository setting

Keep the default `GITHUB_TOKEN` permission read-only and enable only the narrow
ability for Actions to submit pull-request approvals:

```powershell
gh api --method PUT repos/GonzaloTorreras/ai-dememory/actions/permissions/workflow `
  -f default_workflow_permissions=read `
  -F can_approve_pull_request_reviews=true
```

Verify the readback before relying on automation:

```powershell
gh api repos/GonzaloTorreras/ai-dememory/actions/permissions/workflow
```

Expected fields:

```json
{
  "default_workflow_permissions": "read",
  "can_approve_pull_request_reviews": true
}
```

After the bootstrap PR is merged, enforce review freshness and a current base:

```powershell
gh api --method PATCH `
  repos/GonzaloTorreras/ai-dememory/branches/main/protection/required_pull_request_reviews `
  -F dismiss_stale_reviews=true `
  -F require_code_owner_reviews=false `
  -F required_approving_review_count=1 `
  -F require_last_push_approval=true

gh api --method PATCH `
  repos/GonzaloTorreras/ai-dememory/branches/main/protection/required_status_checks `
  -F strict=true `
  -f 'contexts[]=verify'
```

Read back both protection subresources and require `dismiss_stale_reviews`,
`require_last_push_approval`, and `strict` to be `true`, with one approving
review and required context `verify`.

Do not enable broad default write permission. The auto-approval job declares
only `pull-requests: write` plus the read permissions needed to verify the PR,
receipt and CI. It never checks out PR code, restores caches, downloads
artifacts, evaluates PR text as code or accepts fork PRs.

## Bootstrap and security-boundary changes

The first workflow PR cannot approve itself because `issue_comment` uses the
workflow on the default branch. Merge that bootstrap PR only after green CI,
fresh read-only review and an explicit owner instruction. Then enable the two
settings above and verify their readback.

If another open PR was tested before the bootstrap merge, update that branch
from the new `main` so its head changes. Rerun CI, request a fresh review and
post a new tuple-bound receipt; never reuse its earlier green run or review.

Future changes to the listed security-boundary paths are deliberately rejected
by auto-approval. They require the same explicit bootstrap path: green CI,
fresh read-only review, explicit owner instruction, merge without weakening
protections, and immediate readback. This is exceptional maintenance, not the
routine PR path.

`scripts/ci_guard.py` detects accidental workflow drift and backs CI regression
tests. It is not a security boundary against a malicious change; exclusion of
the boundary paths plus the explicit bootstrap review are the enforcement.
