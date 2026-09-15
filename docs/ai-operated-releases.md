# V3 release workflow

This is the current release runbook. V2 scripts, private-vault release receipts,
`intent=recover` and the old task DAG do not apply to the clean V3 package.

Implementation/PR work is separate from authorization to merge, tag and publish.
Obtain user authorization for those gates and a fresh read-only review of the
exact proposed head. Never weaken repository protection or OIDC to finish a run.

1. Update `src/ai_dememory/__init__.py` (dynamic package version) and add a dated,
   nonempty `## [VERSION] - YYYY-MM-DD` changelog section. The date must be the
   dispatch day's UTC date. Summarize the actual alpha limits, not just features.
2. Run focused tests, the complete `tests_v3` suite, compilation and an isolated
   wheel/CLI smoke. CI tests Windows/macOS/Linux, Python 3.11-3.13. The required
   `verify` check aggregates all compatibility matrix jobs.
3. Refresh the PR body with base/head, scope, evidence, tests, remaining risks,
   rollback and approval. Obtain fresh exact-head review and green required CI;
   merge only the reviewed head. Then require green **push CI on current main**.
4. Dispatch `tag-release.yml` from main with `tag=vVERSION`, the exact 40-character
   `approved_sha`, and `confirm=release-vVERSION@SHA`. It verifies current-main
   identity, version/date and green push CI, then creates an immutable annotated
   tag. Tagging alone does not publish.
5. Dispatch `release.yml` from main with the same tag/SHA and
   `confirm=publish-vVERSION@SHA`. There is no `intent` input. The publisher
   rechecks identity and tests, builds once, checks wheel/sdist contents, runs
   installed CLI smoke, records SHA-256 sums and creates artifact attestations.
6. Under the current policy, alpha/beta/RC versions go to **TestPyPI**, final
   versions to **PyPI**. The corresponding GitHub environment and Trusted Publisher
   must authorize `GonzaloTorreras/ai-dememory`, workflow `release.yml`. No static
   publishing token is stored. Changing the target policy requires a reviewed
   workflow change and explicit release-channel choice.
7. The workflow verifies an exact-version installation from that index, then
   creates a GitHub release with the artifacts, checksums and generated notes.
   The checked-in changelog retains the detailed product history.

`publish.yml` is an optional read-only build preflight (`confirm=preflight`),
not an alternate upload or recovery workflow. No package publishing occurs on
ordinary pushes or tag pushes.

## Verification and recovery

Record the merged SHA, CI/tag/publish run URLs, target index/version, artifact
hashes, installed-version readback and any unverified acceptance in the handoff.
Do not call a run published merely because it was dispatched or built.

An environment approval or Trusted Publisher mismatch is an external blocker;
do not substitute credentials or bypass checks. If an upload partly succeeded,
inspect index hashes before retrying; do not overwrite versions or add
`skip-existing` to hide mismatches. Recovery after a successful upload may require
an explicit reviewed fix-forward workflow or a new version, not a blind rerun.

For a bad package, preserve its tag/evidence, obtain approval to yank with a public
reason, annotate the release, and fix forward. Never delete/reuse a public tag or
package version. Local rollback reinstalls the previous wheel; remove owned
integrations first where necessary, never delete a user's memory/account data.
