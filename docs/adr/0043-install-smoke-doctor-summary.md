# ADR 0043: Install Smoke Doctor Summary

## Status

Accepted for the v2 draft.

## Context

ADR 0042 added doctor profile summaries so users and MCP clients can see
whether doctor ran distribution, vault, or unknown-profile checks. The release
checklist already required package and Docker install smoke, but those paths
only checked the plain doctor command. That left the installed CLI and local
Docker image able to regress on the summary contract without failing the smoke
runner.

## Decision

Extend `ai-dememory install-smoke` to run and validate
`doctor --json --summary`:

- the fresh virtual environment package smoke asserts the `vault` profile;
- the local Docker smoke asserts the same profile through `docker run`;
- the assertion verifies JSON shape, summary/check count consistency, and zero
  failing checks.

Plain doctor smoke remains in both paths so existing human-readable output stays
covered.

## Benefits

- Proves the installed package path exposes the doctor profile summary needed by
  users and automation.
- Proves the Docker image sees bind-mounted memory roots as vaults.
- Keeps the summary contract covered before TestPyPI or PyPI publishing.

## Limitations

- Docker validation still depends on Docker being available in the local or CI
  environment.
- The assertion checks the summary shape and failure count, not every individual
  doctor row detail.
- This does not publish or deploy anything; it only strengthens local release
  readiness evidence.

## Future Risks

- If doctor adds severities beyond `ok`, `warn`, and `fail`, smoke validation
  may need to understand how those severities affect release readiness.
- If install smoke gains fast and exhaustive modes, the summary assertion should
  remain in the default release path.
- Remote or cloud distribution paths would need separate profile assertions
  because this ADR only covers local package and Docker stdio flows.

## Dependencies

- ADR 0011 defines the reusable install smoke runner.
- ADR 0041 defines vault versus distribution doctor profile behavior.
- ADR 0042 defines the doctor profile summary contract.
