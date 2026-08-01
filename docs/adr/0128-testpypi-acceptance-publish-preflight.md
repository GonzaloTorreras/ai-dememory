# ADR 0128: TestPyPI Acceptance Publish Preflight Evidence

## Status

Accepted with its evidence source replaced by ADR 0255 on 2026-07-26. TestPyPI
acceptance now comes from the canonical immutable-tag release and post-index
install, never from the legacy readiness preflight.

## Context

The `testpypi-publish` manual acceptance item records real external evidence
from a prerelease. ADR 0255 made `release.yml` the sole publisher and reduced
`publish.yml` to a read-only readiness preflight. A preflight log can support
readiness but cannot prove that any immutable artifact reached TestPyPI.

Manual acceptance is reviewed product-quality and sign-off evidence. It
contributes to local `release_ready` and `publish_ready` planning, but the
canonical publisher cannot read private-vault acceptance receipts and does not
mechanically gate publication on them. Missing or blocked evidence must be
shown in the authorization handoff so the owner can require it or explicitly
accept the residual risk. The tool must never fabricate TestPyPI evidence or
mark the item complete without a reviewed record.

## Decision

The canonical `testpypi-publish` acceptance item is:

`Publish an immutable prerelease tag through the canonical release workflow
only after package and Docker smoke pass, then verify the exact version installs
from TestPyPI.`

Its suggested artifacts are the `release.yml` run URL for the exact immutable
prerelease tag, validation/build/publish/post-index-install logs, the TestPyPI
project/version URL, and a fresh exact-version install smoke log.

Within the local planner, revision 2 is the default stable-release sign-off
evidence. It is not an input consumed by `.github/workflows/release.yml` and
cannot grant or revoke that workflow's publication capability.

## Benefits

- Ties TestPyPI acceptance to the immutable tag and exact workflow that
  performed the upload.
- Proves the published version can be installed back from the external index.
- Prevents the read-only compatibility preflight from being mistaken for
  publication evidence.
- Keeps missing product evidence visible to the release owner without
  misrepresenting a private-vault receipt as a workflow-enforced package gate.

## Limitations

- This still does not publish a package or record acceptance automatically.
- A passing record does not authorize publication, and a missing record is not
  mechanically enforced by the package workflow.
- Reviewers must inspect the GitHub Actions workflow run and record evidence
  manually.
- Reviewers must still inspect index metadata and exact artifact identity; a
  successful workflow URL alone is not sufficient evidence.

## Future Risks

- If canonical release jobs are renamed, suggested artifact text may need an
  update.
- If index verification changes, the acceptance contract must continue to bind
  tag, version, artifact, workflow run, and fresh install evidence.

## Dependencies

- ADR 0016 defines manual acceptance evidence records.
- ADR 0058 defines suggested evidence artifacts in manual acceptance plans.
- ADR 0127 defines hosted readiness smoke.
- ADR 0255 defines the canonical tag publisher and legacy preflight boundary.
- `scripts/manual_acceptance.py` owns the canonical acceptance item registry.
- `docs/release-v2-checklist.md` mirrors the canonical manual acceptance items.
