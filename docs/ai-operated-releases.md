# Agent-Operated, Approval-Gated Releases

## Ownership model

ai-dememory is operationally maintained by Codex and human-account-owned. Codex
has standing authority to implement, test, prepare release PRs, update proposed
versions and changelog entries, collect exact-artifact evidence, coordinate
independent review and prepare fix-forward recovery.

Routine exact-head merge is covered by the owner's standing delegation after
strict CI, a fresh read-only review, and the owner-account receipt. Immutable
tag creation, trusted-publishing dispatch, and package publication remain
important actions that require explicit user authorization. Automated gates
establish technical readiness; they do not grant those release
authorizations. Gonzalo's account or a future organization remains the legal
GitHub and PyPI owner and the destructive break-glass authority.

`release_ready`, `publish_ready`, and manual acceptance are local
product-quality/sign-off evidence. The release handoff must disclose their
remaining blockers, but `.github/workflows/release.yml` cannot read
private-vault receipts and does not enforce those fields. Explicit owner
authorization decides whether any disclosed residual gap is acceptable; the
workflow's hard gates are immutable identity, ancestry, exact artifacts,
tests, attestations, OIDC and post-index installation.

## Canonical flow

1. Codex prepares a normal PR that changes `project.version` and adds a dated
   `CHANGELOG.md` section. Product acceptance reports may accompany the PR but
   do not gate package integrity.
2. CI runs compile, schema, secret, MCP, release, unit, install, package and
   Docker smokes. A fresh read-only reviewer checks the exact PR tuple.
3. Codex presents the exact PR, head/base SHAs, CI and release evidence, obtains
   a fresh `READY` review, posts the exact-tuple `codex-solo-review` receipt,
   and merges with `expected_head_sha` under the standing repository
   delegation. This merge does not authorize a tag or publication.
4. After the reviewed merge and successful CI on `main`, the user explicitly
   dispatches `tag-release.yml` with the exact `v<version>`, the exact
   40-character current-main commit, and
   `confirm=release-<tag>@<approved_sha>`. The workflow rechecks current
   `main`, a successful push-CI run for that SHA, version/changelog identity,
   and immutable-tag collisions before creating the annotated tag. The early
   approval step validates only the exact confirmation and SHA; canonical tag
   syntax is validated once by `ai_release_guard.py` after checkout and before
   any tag mutation, avoiding a second regex that can drift from PEP 440.
5. The tagger stops. It keeps Actions read-only and does not dispatch the
   publisher. The user separately dispatches `release.yml` with `intent`, the
   same exact tag and commit, and
   `confirm=<intent>-<tag>@<approved_sha>`. This is the explicit publication
   authorization and avoids relying on a tag `push` event that GitHub suppresses
   when the tag was created with `GITHUB_TOKEN`.
6. `release.yml` validates repository identity, the exact tag/commit tuple,
   tag syntax, tag-version-changelog alignment and ancestry from `origin/main`.
7. The workflow builds wheel and sdist once, runs `twine check`, installs and
   executes both exact artifacts in isolated environments, generates SHA-256
   checksums and records GitHub artifact attestations.
8. PEP 440 prereleases publish to TestPyPI; final versions publish to PyPI.
   Publishing uses the tag, workflow filename and GitHub environment as the
   Trusted Publisher OIDC identity. No static package token is stored.
9. The workflow installs the exact version from its target index, checks the
   CLI and then creates the GitHub Release with artifacts and checksums.

## Release authorization

There is no repository variable that can convert every future green merge into
a release. Before dispatching the manual tag workflow, all of these must be
true:

- `main` protection is active and the `v*` ruleset rejects deletion and
  non-fast-forward updates, making every existing release tag immutable;
- while the repository remains under a personal owner, GitHub does not accept
  its native Actions integration as a repository-ruleset bypass actor. New tag
  creation is therefore limited by repository write access plus the exact,
  manual tagger. A direct tag does not trigger publication. If the repository
  moves to an organization or installs a dedicated tagger App, add the
  creation rule with only that installed integration as bypass before treating
  creation as ruleset-enforced;
- GitHub environments `testpypi` and `pypi` exist with the intended approval
  policy and no alternate publisher identity;
- PyPI and TestPyPI Trusted Publishers point exactly to
  `GonzaloTorreras/ai-dememory`, `.github/workflows/release.yml`, and their
  matching environment;
- an RC tag has completed the TestPyPI and post-install path;
- the recovery runbook has been exercised without uploading a duplicate;
- the owner has approved the exact tag and commit tuple shown in the dispatch.

A green CI run or reviewed merge with a new version is never tag or publication
authorization by itself. Creating the approved tag does not trigger
publication. Tag authorization and publication authorization are two separate
manual dispatches, each bound to the same immutable tuple. `release.yml` is intentionally
`workflow_dispatch`-only, so a direct `v*` push is not a publisher path.

`.github/workflows/publish.yml` is not a recovery publisher. It is a retained
manual, read-only readiness preflight with `confirm=preflight`. It has no OIDC,
package environment, artifact-transfer, tag-push, release-creation, or upload
capability. Both package-index Trusted Publisher identities must reference only
`.github/workflows/release.yml`.

## Recovery and rollback

`release.yml` accepts `intent=recover` for an existing tag and requires the
exact confirmation `recover-<tag>@<approved_sha>`. The dispatch itself requires
explicit user approval. It checks out and republishes only that exact immutable
identity. PyPI versions and tags are never overwritten or reused. If an
artifact is already present, compare index hashes with `SHA256SUMS`; mismatch
is an incident, not a reason to use `skip-existing`.

For a bad release:

1. preserve the tag, workflow run and attestation;
2. yank the PyPI version with a public reason;
3. annotate the GitHub Release and open an incident issue;
4. fix forward with a new patch version and changelog entry;
5. never delete the release as a substitute for provenance.

Account recovery, legal or billing changes, trusted-publisher ownership changes,
compromise and destructive break-glass remain separately human-controlled.

## Lessons incorporated from Clawpatch

- one canonical release workflow owns validation, publication and GitHub
  Release creation;
- tag-version-changelog alignment is checked before publishing;
- the packed artifact is installed into an isolated temporary environment and
  the installed CLI is exercised against a synthetic fixture;
- release evidence includes package URLs, checksums, CI/run URLs and test proof;
- workflow, documentation and agent-facing release instructions are changed
  together so release skills cannot drift from the actual OIDC path.
