# ADR 0258: Explicit Release Tag Authorization

## Status

Accepted by the Codex Operational Owner under explicit owner-delegated
repository authority on 2026-07-27.

## Context

The release tagger previously ran after every successful push CI on `main` when
the repository variable `AI_RELEASE_ENABLED` was true. That switch was a
one-time configuration decision, not approval for a particular future
version/commit tuple. Once enabled, an ordinary merge containing a new version
could create a tag and trigger trusted publication without a new explicit
release action. This contradicted the repository rule that tag creation and
publication require owner authorization.

## Decision

Make `.github/workflows/tag-release.yml` manual and bind authorization to exact
immutable inputs:

- `tag` is the exact `v<project.version>` identity;
- `approved_sha` is an exact 40-character commit;
- `confirm` must equal `release-<tag>@<approved_sha>`;
- the workflow checks out only that SHA with persisted credentials disabled;
- GitHub API readback must prove the SHA is current `main` and has a successful
  completed push run of the canonical CI workflow;
- `ai_release_guard.py` must prove tag/version/changelog identity before any
  write;
- an existing tag is accepted only if it resolves to the approved SHA;
- a new annotated tag is created through the GitHub API and only then triggers
  the sole publisher in `release.yml`.

Remove `workflow_run` and `AI_RELEASE_ENABLED` from the tagger. Recovery remains
a separate manual `release.yml` dispatch for an existing immutable tag with
`confirm=recover-<tag>`.

This ADR supersedes the automatic-tagger and migration-switch clauses in ADRs
0247, 0252, and 0255. Their protected-main, immutable artifact, single
publisher, OIDC, provenance, and explicit-authorization requirements remain.

## Consequences

A green merge no longer publishes by ambient repository configuration. Release
authorization is inspectable, replay-resistant at the tuple level, and
separate from merge authorization. The operator performs one additional manual
dispatch after green `main`; publication remains automated after the approved
tag is created.

## Limitations

Repository maintainers can still create tags through other GitHub surfaces, so
branch/ruleset and account security remain part of the trust boundary. Workflow
text guards are defense in depth, not a substitute for GitHub environment and
Trusted Publisher configuration. The CI API check proves a successful recorded
run, not the absence of a compromised action.

## Future Risks

A later workflow could reintroduce an automatic tag trigger, weaken the
confirmation tuple, accept a stale main SHA, or add another package publisher.
Workflow supply-chain and publisher-inventory guards must remain release gates.

## Dependencies

- ADR 0252 defines readiness versus owner authorization.
- ADR 0255 defines the single canonical publisher.
- `.github/workflows/tag-release.yml` creates the explicitly approved tag.
- `.github/workflows/release.yml` validates and publishes only immutable tags.
- `scripts/publish_guard.py` enforces the manual tagger and publisher topology.

## Rollback

Fail closed by leaving the tag workflow undispatched. Recover an interrupted
publication only from the existing immutable tag through the guarded
`release.yml` recovery dispatch. Reintroducing ambient or automatic tag
creation requires a new owner-accepted ADR and matching threat review.
