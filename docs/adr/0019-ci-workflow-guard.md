# ADR 0019: CI Workflow Guard

## Status

Accepted for v2 draft.

## Context

The release checklist depends on GitHub Actions running compile, schema,
secret-scan, MCP contract, release-check, unit, recall, package install, and
Docker local MCP smoke gates. Before this ADR, `ai-dememory release-check`
validated publish workflow safety but did not validate that CI still contained
the required v2 verification commands.

That left a drift risk: a future edit to `.github/workflows/ci.yml` could remove
package install smoke or Docker smoke while local release checks still appeared
healthy.

## Decision

Add `ai-dememory ci-guard`, backed by `scripts/ci_guard.py`, and make
`ai-dememory release-check` run it.

The guard verifies that `.github/workflows/ci.yml`:

- runs on pull requests and pushes to `main`
- uses Python 3.12
- runs compile, validate, secret-scan, verify-mcp, release-check, unit tests,
  PR-gated MCP runtime smoke, index/search smoke, recall evaluation, package
  install smoke, and Docker local MCP smoke commands
- runs a final package build artifact guard after package install, package
  build, and Docker local MCP smoke commands

The guard is dependency-free and text-based like `publish_guard.py`.

## Benefits

- Makes CI drift visible during local release checks.
- Protects package install and Docker smoke coverage from accidental removal.
- Protects PR-gated MCP runtime smoke coverage from accidental removal.
- Protects the final post-smoke package build artifact boundary from accidental
  removal.
- Keeps release readiness evidence aligned with the actual GitHub Actions file.
- Avoids introducing a YAML parser dependency for a small workflow contract.

## Limitations

- Text checks can miss semantically equivalent workflow rewrites.
- The guard confirms commands are present, not that GitHub-hosted runners will
  pass at runtime.
- It does not inspect workflow permissions beyond the publish workflow guard.

## Future Risks

- If CI moves to reusable workflows, matrix jobs, or composite actions, the guard
  may need structured parsing or explicit allowlisted reusable workflow names.
- If Python versions change, this ADR and guard must be updated together.
- ADR 0106 adds a required post-smoke package build artifact guard after all
  smoke commands.
- ADR 0107 adds a required PR-gated MCP runtime smoke in CI.
