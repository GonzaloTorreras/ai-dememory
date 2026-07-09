# ADR 0105: Package Build Stale Artifact Preflight

## Status

Accepted.

## Context

ADR 0077 added `ai-dememory package-build-smoke` so maintainers can build a
wheel and source distribution in temporary output and run `twine check` before
publishing. The smoke preserved pre-existing generated build paths in the source
checkout because deleting unknown local files is unsafe.

On Windows, stale `build/` or `ai_dememory.egg-info/` metadata can cause the
build backend to fail with low-level access-denied errors while it rewrites
package metadata. That failure is noisy and does not clearly tell maintainers
that cleanup is required before rerunning the smoke.

## Decision

Add a package-build-smoke preflight that refuses to run when generated package
build paths already exist in the repository checkout.

The preflight checks `build/`, `dist/`, and `ai_dememory.egg-info/`. If any are
present, it raises an `InstallSmokeError` that names the stale generated paths
and instructs maintainers to remove generated package build artifacts before
rerunning the smoke.

Share generated build artifact cleanup between install smoke and package-build
smoke. Install smoke snapshots pre-existing generated paths before package
installation and removes only generated paths it created, so running
`install-smoke` before `package-build-smoke` does not leave stale local package
metadata behind.

## Benefits

- Replaces backend-specific access-denied failures with a clear release-gate
  diagnostic.
- Avoids deleting pre-existing local files without explicit maintainer action.
- Keeps package-build smoke aligned with artifact-guard expectations.
- Keeps the documented install-smoke then package-build-smoke release sequence
  reproducible in a clean checkout.

## Limitations

- The preflight is intentionally conservative and refuses to clean stale paths
  automatically.
- It only checks the known package build output paths.
- It does not prevent the build backend from creating temporary metadata during
  a clean run; cleanup still removes paths created by the smoke.
- Install smoke cleanup uses the same generated path list, so newly supported
  package build outputs must be added once for both smoke commands.

## Future Risks

- If package build tooling starts writing different generated paths, the
  preflight list must be updated with artifact-guard coverage.
- If maintainers want automatic cleanup, that should be an explicit flag rather
  than default behavior.
- If a stale path is held by another process, maintainers still need to release
  that lock before rerunning.

## Dependencies

- ADR 0020 defines generated artifact staging boundaries.
- ADR 0077 defines package-build smoke.
- `scripts/build_artifacts.py` defines shared generated package build artifact
  cleanup.
- `scripts/package_build_smoke.py` remains the executable package-build smoke
  implementation.
