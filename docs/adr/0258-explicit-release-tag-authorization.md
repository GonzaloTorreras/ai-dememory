# ADR 0258: Explicit Release Tag And Publication Authorization

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
- a new annotated tag is created through the GitHub API;
- the tagger keeps Actions read-only and never dispatches the publisher;
- `release.yml` is `workflow_dispatch`-only and requires a second explicit
  `intent`, tag, commit and
  `confirm=<intent>-<tag>@<approved_sha>` authorization before publishing.

Remove `workflow_run` and `AI_RELEASE_ENABLED` from the tagger. Recovery remains
a separate manual `release.yml` dispatch for an existing immutable tag with
`intent=recover` and `confirm=recover-<tag>@<approved_sha>`.

This ADR supersedes the automatic-tagger and migration-switch clauses in ADRs
0247, 0252, and 0255. Their protected-main, immutable artifact, single
publisher, OIDC, provenance, and explicit-authorization requirements remain.

## Consequences

A green merge no longer publishes by ambient repository configuration. Release
authorization is inspectable, replay-resistant at the tuple level, and
separate from merge authorization. The operator performs two manual dispatches
after green `main`: one creates the exact tag and the other authorizes the
publisher for that same tuple. Artifact build, publication and verification
remain automated after the second dispatch.

## Limitations

Repository maintainers can still create tags through other GitHub surfaces, so
the `v*` creation ruleset and account security remain part of the trust
boundary. A direct tag no longer triggers the current publisher, but tagging an
older commit could select its historical workflow unless tag creation is
restricted to the GitHub Actions integration. Workflow text guards are defense
in depth, not a substitute for ruleset, environment and Trusted Publisher
configuration. The CI API check proves a successful recorded run, not the
absence of a compromised action.

## Future Risks

A later workflow could reintroduce an automatic tag trigger or tagger-driven
publisher dispatch, weaken either confirmation tuple, accept a stale main SHA,
or add another package publisher.
Workflow supply-chain and publisher-inventory guards must remain release gates.

## Dependencies

- ADR 0252 defines readiness versus owner authorization.
- ADR 0255 defines the single canonical publisher.
- `.github/workflows/tag-release.yml` creates the explicitly approved tag.
- `.github/workflows/release.yml` validates and publishes only immutable tags.
- `scripts/publish_guard.py` enforces the manual tagger and publisher topology.

## Rollback

Fail closed by leaving either workflow undispatched. Recover an interrupted
publication only from the existing immutable tag through the guarded exact
tuple `release.yml` recovery dispatch. Reintroducing ambient tag publication or
automatic publisher dispatch requires a new owner-accepted ADR and matching
threat review.
