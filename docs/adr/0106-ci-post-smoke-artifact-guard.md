# ADR 0106: CI Post-Smoke Package Build Artifact Guard

## Status

Accepted.

## Context

CI already runs `artifact-guard` before package install, package build, and
Docker smoke gates. Those smokes exercise build and install paths that can
create generated package metadata in the checkout.

Running the guard only before the smokes proves the starting checkout is clean,
but it does not prove the smoke commands clean up package build metadata after
themselves. ADR 0105 made stale generated package build artifacts a
release-blocking condition, so CI should also catch smoke residue before a
branch looks releasable.

## Decision

Add `python scripts/ai_dememory.py package-build-smoke --check-clean`, a
preflight-only mode that checks the known generated package build paths without
building distributions.

Run that check at the end of the CI verification job, after Docker local MCP
smoke.

Strengthen `scripts/ci_guard.py` so it requires:

- the existing early artifact guard
- a named `Final package build artifact guard` step
- the final package build artifact guard command after Docker local MCP smoke

## Benefits

- Proves install, package build, and Docker smoke commands do not leave known
  generated package build metadata in the checkout.
- Catches workflow drift if the final cleanup check is removed or moved before
  the smoke commands.
- Keeps CI aligned with package-build stale artifact preflight behavior.

## Limitations

- The guard only checks `build/`, `dist/`, and `ai_dememory.egg-info/`; it does
  not inspect unrelated generated index, report, or cache paths because earlier
  CI smoke commands intentionally create some of those artifacts.
- Text-based workflow validation can reject semantically equivalent rewrites
  until the guard is updated.
- The final package build artifact guard still checks known local package build
  paths, not every untracked file that a tool could create.

## Future Risks

- If CI moves smoke gates into separate jobs, the final package build artifact
  guard must move into each job that can create package build metadata or run
  after shared artifacts are downloaded.
- If smoke commands intentionally keep generated evidence, that evidence must be
  moved under an ignored/reviewed artifact path or the guard contract must be
  revised.
- If generated artifact policy expands beyond package build paths, the final CI
  check may need a separate cleanup or working-tree artifact verifier.

## Dependencies

- ADR 0019 defines the CI workflow guard.
- ADR 0020 defines generated artifact staging boundaries.
- ADR 0105 defines stale package build artifact preflight behavior.
- `.github/workflows/ci.yml` remains the GitHub Actions verification workflow.
- `scripts/ci_guard.py` remains the executable CI workflow contract.
