# ADR 0252: Review-Gated Agent Operations

## Status

Accepted by the Codex Operational Owner under explicit owner-delegated
repository authority on 2026-07-26.

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

Keep the immutable-tag release and tuple-bound auto-approval mechanisms, with
these authority boundaries:

- Codex owns routine implementation, maintenance, branch preparation, test and
  release evidence, documentation, version proposals, changelog proposals, and
  fix-forward planning.
- A fresh independent read-only review is required before a pull request is
  marked ready or presented for merge.
- Merge, release-tag dispatch, publisher dispatch, package publication,
  repository visibility changes, and secret or trusted-publisher changes
  require explicit authorization from the repository owner.
- The `github-actions[bot]` review is evidence that the exact PR tuple passed
  the configured technical checks. It is not owner authorization.
- Tag and publication authorizations are separate manual actions bound to the
  exact tag and current-main SHA; approval to merge does not implicitly approve
  either dispatch.
- Evidence generated from the historical private source checkout is not valid
  for the public repository. Changes must be ported onto public `origin/main`
  and validated again against the resulting public commit.

This ADR supersedes the no-human-approval clauses in ADR 0247 and ADR 0251.
Their immutable-artifact, OIDC, provenance, independent-review, and tuple-bound
validation decisions remain in force.

## Consequences

Codex can continue development autonomously through an approve-ready pull
request and can repair findings without waiting for routine instructions. It
must stop at the exact important action that needs owner authorization. Release
handoffs must clearly identify the PR, commit tuple, version, successful checks,
artifact evidence, and both exact manual dispatch tuples.

Existing auto-approval workflows may continue to provide an auditable technical
review signal. Documentation and future automation must not describe that signal
as permission to merge or publish.

## Limitations

This policy cannot cryptographically prove that an instruction came from the
legal account owner; the execution environment and GitHub permissions remain
part of the trust boundary. It also introduces an intentional wait at merge and
release boundaries even when every technical check is green.

## Future Risks

New automation could accidentally collapse readiness and authorization again,
especially if a default-branch workflow creates tags immediately after merge.
Wording drift across runbooks, ADRs, workflow names, and bot comments could also
mislead maintainers unless guarded by tests or periodic documentation review.

## Dependencies

- ADR 0247 defines immutable-tag package releases.
- ADR 0251 defines tuple-bound technical auto-approval.
- ADR 0258 defines separate tuple-bound tag and publication authorization.
- `AGENTS.md` defines repository authority and approval boundaries.
- `.github/workflows/tag-release.yml` and `.github/workflows/release.yml`
  implement the release path.
- `docs/auto-approval.md` documents the trusted bot-review boundary.

## Rollback

Fail closed: if authorization is absent, ambiguous, stale, or does not cover the
publication consequence, do not merge, tag, dispatch, or publish. Changing this
boundary requires a new owner-accepted ADR and corresponding policy, workflow,
guard, and documentation review; editing historical evidence is not a rollback.
