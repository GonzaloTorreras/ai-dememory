# ADR 0128: TestPyPI Acceptance Publish Preflight Evidence

## Status

Accepted.

## Context

The `testpypi-publish` manual acceptance item previously required publishing to
TestPyPI only after package and Docker smoke passed in CI. ADR 0127 moved those
same smoke gates into the manual publish workflow preflight, so the acceptance
item should now require evidence from both the PR/CI path and the exact publish
workflow run.

Manual acceptance remains the release boundary for external publishing. The tool
must not fabricate TestPyPI evidence or mark the item complete without a
reviewed record.

## Decision

Update the canonical `testpypi-publish` acceptance item to:

`Publish to TestPyPI only after package and Docker smoke pass in CI and publish
workflow preflight.`

Also update the suggested artifacts for that item to include the publish
workflow preflight log showing install smoke, package build smoke, and Docker
local MCP smoke.

## Benefits

- Aligns manual acceptance with the stronger publish workflow gate.
- Ties TestPyPI approval to the exact workflow run that performed the upload.
- Keeps release evidence from accepting CI-only proof after publish preflight was
  added.
- Gives reviewers a clearer artifact to attach before recording acceptance.

## Limitations

- This still does not publish a package or record acceptance automatically.
- Reviewers must inspect the GitHub Actions workflow run and record evidence
  manually.
- The evidence can prove the workflow gates ran, but not that external TestPyPI
  metadata is correct unless reviewers inspect the published package.

## Future Risks

- If publish workflow jobs are renamed, suggested artifact text may need an
  update.
- If publishing moves to signed tags, the acceptance record should include the
  tag ref and workflow URL.
- If TestPyPI install verification becomes automated in the publish workflow,
  the acceptance item should require that log too.

## Dependencies

- ADR 0016 defines manual acceptance evidence records.
- ADR 0058 defines suggested evidence artifacts in manual acceptance plans.
- ADR 0127 defines publish workflow smoke gates.
- `scripts/manual_acceptance.py` owns the canonical acceptance item registry.
- `docs/release-v2-checklist.md` mirrors the canonical manual acceptance items.
