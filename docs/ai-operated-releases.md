# V3 release workflow

Codex operates routine PRs, reviewed merges, tags and PyPI releases under the
user's standing authorization for this repository. Do not request the same
approval again for each routine release. Fresh independent exact-head review,
green CI and normal environment approval still apply. Secrets, deployment,
visibility and destructive operations are separate boundaries.

## One maintainer action, then automated publication

1. Update `src/ai_dememory/__init__.py` and add a nonempty dated
   `## [VERSION] - YYYY-MM-DD` changelog section. Use the dispatch day's UTC date.
   Explain actual limits as well as changes.
2. Run focused tests, all `tests_v3`, compilation and isolated wheel/CLI smoke.
   Refresh the PR handoff with base/head, paths, evidence, risk and rollback.
   Obtain a fresh independent read-only review, then merge the exact green head.
   Require green **push CI on current main** before tagging.
3. Dispatch `tag-release.yml` from main with `tag=vVERSION`, the exact
   `approved_sha` and `confirm=release-vVERSION@SHA`. It validates current main,
   source version/date and push CI, then creates an immutable annotated tag.
4. The tagger's separate, no-checkout dispatch job starts `release.yml` on main
   with the identical tag/SHA and generated publication confirmation. Its only
   extra capability is `actions: write`; it cannot upload packages or mint OIDC.
   The publisher remains standalone to preserve its Trusted Publisher identity.
5. The publisher rechecks tag/main identity and tests, builds once, inspects the
   wheel/sdist, runs installed CLI smoke and records checksums/attestations.
   All reviewed versions, **including alpha/beta/RC**, go to **production PyPI**.
   Pre-release versions retain their suffix and GitHub prerelease flag; this
   does not declare them stable. TestPyPI is no longer the delivery channel.
6. The existing `pypi` environment reviewer rule remains. The maintainer handles
   its normal approval under the standing authority; this is not a protection
   bypass or an entirely unattended environment. OIDC must authorize owner
   `GonzaloTorreras`, repository `ai-dememory`, workflow `release.yml`, environment
   `pypi`. No static publishing token is stored.
7. Verify exact-version installation from PyPI, then create the GitHub release
   with the built artifacts, checksums and generated notes. Read back the actual
   index/release before reporting success.

The standalone publisher also accepts a maintainer dispatch with the same tuple
and `confirm=publish-vVERSION@SHA` for deliberate recovery, not blind retries.
Ordinary pushes/tag pushes do not publish. `publish.yml` is an optional read-only
build preflight (`confirm=preflight`), not another upload workflow.

GitHub token-created tag events do not trigger another workflow; explicit
[workflow dispatch](https://docs.github.com/en/actions/concepts/security/github_token)
does. Keeping the publisher standalone also avoids the current
[PyPI reusable-workflow limitation](https://docs.pypi.org/trusted-publishers/troubleshooting/#reusable-workflows-on-github).

## Verification and recovery

Record merged SHA, CI/tag/publish URLs, index/version and published hashes in the
PR handoff. Private vault/install evidence stays private. A dispatched/built job
is not a published release.

Handle environment approval normally. A Trusted Publisher mismatch requires
one-time owner configuration; do not substitute credentials or weaken protection.
If an upload partly succeeded, inspect index hashes before retrying. Do not use
`skip-existing`, overwrite versions or replace tags. Use reviewed fix-forward
recovery or a new version.

For a bad package, preserve tag/evidence, obtain approval to yank with a public
reason, annotate the release and fix forward. Local rollback reinstalls the prior
wheel; never delete a user's memory or account data.
