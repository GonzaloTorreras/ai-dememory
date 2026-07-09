# ADR 0056: Install Smoke Maintenance Artifact Status

Status: Accepted for the v2 draft.

## Context

ADR 0055 added generated artifact visibility to `maintenance status` and MCP
`memory.maintenance_status`. Package install smoke already ran
`ai-dememory maintenance status` from a fresh installed CLI environment, but it
only checked the command exit code.

The installed package path is the main user setup path, so smoke coverage should
verify the JSON status shape that scheduler and MCP users rely on.

## Decision

Package install smoke now validates that installed
`ai-dememory maintenance status` returns a generated artifact map containing:

- `index`
- `graph`
- `weights`
- `lifecycle_scores`
- `lifecycle_report`

Each artifact entry must include a path, an existence boolean, and optional
timestamp and size fields with the expected types.

## Benefits

- Ensures the installed CLI exposes the maintenance artifact status contract.
- Catches packaging or import drift that would otherwise leave scheduler setup
  without artifact visibility.
- Keeps install smoke aligned with ADR 0055 and MCP runtime smoke.

## Limitations

- The package smoke only validates status shape in a temporary vault.
- It does not require all artifacts to exist before daily maintenance runs.
- Docker install smoke remains a separate runtime path.

## Future Risks

- New generated artifacts must be added to both maintenance status and this
  install-smoke validator.
- If maintenance status moves away from JSON-by-default output, the smoke must
  pass an explicit `--json` flag or adapt to the new contract.

## Dependencies

- ADR 0011 defines the reusable install smoke runner.
- ADR 0055 defines generated artifact visibility in maintenance status.
- `scripts/install_smoke.py` remains the package install smoke implementation.
