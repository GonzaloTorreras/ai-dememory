# ADR 0076: Publish Workflow Preflight

Status: Superseded for publication behavior by ADR 0255 on 2026-07-26. The
preflight checks remain, but `.github/workflows/publish.yml` no longer builds,
transfers, or publishes distributions and now requires `confirm=preflight`.

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

Historical decision, superseded as described in Status: the original workflow
added a `preflight` job to
`.github/workflows/publish.yml` between confirmation validation and
distribution build.

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

The original `build` job depended on `preflight`.

Under ADR 0255, the preflight and its checks remain but the downstream build and
publisher jobs no longer exist. `publish-guard` now enforces that the hosted
preflight stays read-only and non-publishing.

## Benefits

- Prevents a hosted readiness handoff when fast repository safety checks fail.
- Keeps the compatibility workflow aligned with local release gates.
- Reuses existing guards instead of duplicating publish safety policy in docs.
- Prevents a legacy hosted readiness run from bypassing fresh package and Docker
  smoke for the selected ref.

## Limitations

- `release-check` runs without a PR URL in manual publish context, so it can
  warn about the PR gate but still catch source and documentation failures.
- This does not prove TestPyPI/PyPI trusted-publisher configuration.
- It does not replace manual acceptance or release authorization.
- Hosted preflight runtime is longer and depends on Docker availability.

## Future Risks

- The canonical publisher now starts from protected release tags; this legacy
  preflight must not be treated as tag evidence.
- If `release-check` becomes strict-by-default, publish workflow handling for
  PR-gate warnings must be revisited.
- If package smoke starts leaving checkout-local build artifacts, the preflight
  must still discard them.

## Dependencies

- ADR 0255 defines the current sole-publisher boundary.
- ADR 0019 defines CI workflow guard coverage.
- ADR 0020 defines generated artifact staging boundaries.
- ADR 0127 defines publish preflight smoke gates.
- `scripts/publish_guard.py` remains the executable publish workflow contract.
- `.github/workflows/publish.yml` remains manual, `confirm=preflight`,
  read-only, and non-publishing.
