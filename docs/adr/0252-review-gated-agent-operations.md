# ADR 0252: Review-Gated Agent Operations

## Status

Accepted by the Codex Operational Owner under explicit owner-delegated
repository authority on 2026-07-26. ADR 0260 superseded the per-merge explicit
authorization and bot-review mechanics for routine repository changes on
2026-08-04; its release, publication, visibility, secret, destructive, and
production-operation gates remain in force.

## Context

Codex is the operational owner of ai-dememory and should be able to implement,
test, document, review, and prepare releases without routine operator
micromanagement. ADR 0247 introduced immutable-tag releases and ADR 0251
introduced a tuple-bound bot approval after an independent read-only review.
Both are valuable technical controls, but their original wording also treated
green automation as sufficient authority to merge and publish.

Repository policy now distinguishes technical readiness from authorization for
important actions. A bot identity can satisfy a branch-protection review rule,
but it cannot express the repository owner's intent to merge a particular
change or publish a particular package.

## Decision

Keep immutable-tag release controls and the following authority boundaries:

- Codex owns routine implementation, maintenance, branch preparation, exact-head
  merge, test and release evidence, documentation, version proposals, changelog
  proposals, and fix-forward planning under the owner's standing delegation.
- A fresh independent read-only review is required before a pull request is
  marked ready or presented for merge.
- Routine merge requires the exact-tuple owner receipt defined by ADR 0260,
  strict CI, no unresolved findings, and an expected-head API merge. It does not
  require a GitHub approving review or a repeated owner confirmation.
- Release-tag dispatch, publisher dispatch, package publication, production
  deployment, repository visibility changes, and secret or trusted-publisher
  changes require explicit authorization from the repository owner.
- Tag and publication authorizations are separate manual actions bound to the
  exact tag and current-main SHA; a reviewed merge does not implicitly approve
  either dispatch.
- Evidence generated from the historical private source checkout is not valid
  for the public repository. Changes must be ported onto public `origin/main`
  and validated again against the resulting public commit.

This ADR supersedes the no-human-approval clauses in ADR 0247. ADR 0260 later
supersedes its routine-merge and bot-review mechanics. Immutable-artifact, OIDC,
provenance, independent-review, and tuple-bound validation decisions remain in
force.

## Consequences

Codex can continue development and routine exact-head merges autonomously after
the required independent review and owner-account receipt. It must stop at the
exact high-risk action that needs owner authorization. Release handoffs must
clearly identify the PR, commit tuple, version, successful checks, artifact
evidence, and both exact manual dispatch tuples.

## Limitations

This policy cannot cryptographically prove that a subagent ran or that an
instruction came from the legal account owner; the execution environment and
GitHub permissions remain part of the trust boundary. It introduces an
intentional wait at release and production boundaries even when every technical
check is green.

## Future Risks

New automation could accidentally collapse readiness and high-risk authorization
again, especially if a default-branch workflow creates tags immediately after
merge. Wording drift across runbooks, ADRs, and owner receipts could also mislead
maintainers unless guarded by tests or periodic documentation review.

## Dependencies

- ADR 0247 defines immutable-tag package releases.
- ADR 0251 records the superseded tuple-bound bot-approval design.
- ADR 0260 defines current sole-maintainer review receipts and routine merge.
- ADR 0258 defines separate tuple-bound tag and publication authorization.
- `AGENTS.md` defines repository authority and approval boundaries.
- `.github/workflows/tag-release.yml` and `.github/workflows/release.yml`
  implement the release path.
- `docs/solo-maintainer-review.md` documents the current review boundary.

## Rollback

Fail closed: if authorization is absent, ambiguous, stale, or does not cover the
publication consequence, do not merge, tag, dispatch, or publish. Changing this
boundary requires a new owner-accepted ADR and corresponding policy, workflow,
guard, and documentation review; editing historical evidence is not a rollback.
