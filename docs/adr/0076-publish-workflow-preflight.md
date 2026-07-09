# ADR 0076: Publish Workflow Preflight

Status: Accepted for the v2 draft.

## Context

The manual GitHub Actions publishing workflow already required
`workflow_dispatch`, `confirm=publish`, TestPyPI/PyPI environment selection, and
PyPI Trusted Publishing. It built distributions and ran `twine check` before
upload.

That protected the upload mechanism, but it did not run the repository's own
release safety checks inside the publish workflow. A maintainer could manually
start a publish run from a branch where the package builds but source-level
guards, schema validation, secret scanning, MCP contract validation, or release
readiness checks would fail locally or in CI.

## Decision

Add a `preflight` job to `.github/workflows/publish.yml` between confirmation
validation and distribution build.

The preflight job runs:

- `python -m compileall -q scripts mcp/server ai_dememory_tool`
- `python scripts/ai_dememory.py publish-guard`
- `python scripts/ai_dememory.py artifact-guard`
- `python scripts/ai_dememory.py validate`
- `python scripts/ai_dememory.py secret-scan`
- `python scripts/ai_dememory.py verify-mcp`
- `python scripts/ai_dememory.py release-check`
- `python scripts/ai_dememory.py install-smoke`
- `python scripts/ai_dememory.py package-build-smoke --check-clean`
- `python scripts/ai_dememory.py install-smoke --skip-package --docker --image ai-dememory:publish`

The `build` job now depends on `preflight`.

`publish-guard` enforces that the workflow keeps the preflight job, the build
dependency, and the required commands. The smoke commands run in the preflight
workspace; the publish distribution build still uses a separate job with a fresh
checkout.

## Benefits

- Prevents manual package publishing when fast repository safety checks fail.
- Keeps the publish workflow aligned with local v2 release gates.
- Reuses existing guards instead of duplicating publish safety policy in docs.
- Prevents manual TestPyPI/PyPI dispatch from bypassing fresh package and Docker
  smoke for the selected ref.

## Limitations

- `release-check` runs without a PR URL in manual publish context, so it can
  warn about the PR gate but still catch source and documentation failures.
- This does not prove TestPyPI/PyPI trusted-publisher configuration until the
  GitHub environments are actually configured.
- It does not replace manual acceptance or publish approval.
- Publish runtime is longer and depends on Docker availability.

## Future Risks

- If the publish workflow starts from protected release tags instead of
  branches, the preflight job may need tag-specific release evidence.
- If `release-check` becomes strict-by-default, publish workflow handling for
  PR-gate warnings must be revisited.
- If package smoke starts leaving checkout-local build artifacts, the build job
  must stay isolated from preflight.

## Dependencies

- ADR 0012 defines the manual Trusted Publishing guard.
- ADR 0019 defines CI workflow guard coverage.
- ADR 0020 defines generated artifact staging boundaries.
- ADR 0127 defines publish preflight smoke gates.
- `scripts/publish_guard.py` remains the executable publish workflow contract.
- `.github/workflows/publish.yml` remains manual-only and confirmation-gated.
