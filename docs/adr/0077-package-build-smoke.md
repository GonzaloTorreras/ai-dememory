# ADR 0077: Package Build Smoke

Status: Accepted for isolated package-build validation. References to the
legacy manual workflow building or uploading were superseded by ADR 0255 on
2026-07-26.

## Context

The release path checks installed-package behavior through `install-smoke`, but
normal CI also needs to prove independently that the source tree can build both
a wheel and source distribution and that the resulting metadata passes
`twine check`.

Running package builds directly in the repository workspace can also leave
generated `dist/`, `build/`, or egg-info artifacts that are easy to stage by
mistake. The release path needs an explicit package-build check that keeps build
output outside the repository by default.

## Decision

Add `ai-dememory package-build-smoke`.

The command creates a temporary virtual environment, installs `build` and
`twine`, builds the repository into a temporary `dist` directory, requires
exactly one wheel and one source distribution, runs `twine check` on those
artifacts, and deletes the temporary directory unless `--keep-temp` is supplied.

CI, the pull request template, local guard scripts, release readiness docs, and
the v2 checklist all include the command as a required release gate.

## Benefits

- Proves package metadata and distribution builds before an immutable-tag
  release is authorized.
- Keeps wheel and source distribution artifacts out of the repository workspace.
- Makes the release checklist executable through CI and local guard scripts.
- Gives maintainers a focused command for package-build failures without
  invoking the canonical release workflow.

## Limitations

- The check does not publish to TestPyPI or PyPI.
- The check installs current `build` and `twine` versions from the configured
  Python package indexes, so package-index outages can fail the smoke.
- It validates distribution shape and metadata, not every installed CLI command;
  that remains covered by `install-smoke`.

## Future Risks

- If the project starts producing multiple wheel variants, the exactly-one-wheel
  assertion will need to become platform aware.
- If the build backend starts writing metadata beside the source tree, artifact
  guard coverage must remain strict enough to catch it.
- ADR 0105 later adds a fail-fast preflight for stale generated package build
  paths before invoking the build backend.
- Canonical tag/version consistency remains a separate `release.yml` gate; this
  smoke must not claim immutable-tag provenance.

## Dependencies

- ADR 0255 defines the sole canonical publisher.
- ADR 0019 defines CI workflow guard coverage.
- ADR 0020 defines generated artifact staging boundaries.
- ADR 0076 retains the hosted readiness-preflight rationale.
- ADR 0105 defines stale generated package build artifact preflight behavior.
- `scripts/package_build_smoke.py` is the executable package-build contract.
