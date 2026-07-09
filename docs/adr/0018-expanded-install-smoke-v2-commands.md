# ADR 0018: Expanded Install Smoke For v2 Commands

## Status

Accepted for v2 draft.

## Context

`ai-dememory install-smoke` verifies the package from an installed environment
instead of the source checkout. As v2 added provenance audits, manual acceptance
evidence, and recall fixture promotion, those commands became part of the user
setup surface but were not covered by the fresh-package smoke runner.

Relying only on unit tests and source-checkout commands can miss packaging,
console-script, import-path, and template issues that users would hit after
installing the tool with `pipx`, `uv tool`, or a wheel.

## Decision

Expand `scripts/install_smoke.py` so the package smoke also verifies:

- `ai-dememory provenance --json`
- `ai-dememory acceptance status --json`
- `ai-dememory acceptance verify --help`
- `ai-dememory recall-fixtures promote-miss --help`
- `ai-dememory schedule setup --dry-run --mode docker --image ai-dememory:local`
- `ai-dememory schedule cron --json`
- `ai-dememory review modes`
- `ai-dememory review plan --kind conflict`
- a full local recall miss capture and fixture promotion inside the temporary
  vault, followed by `ai-dememory eval-recall`

The smoke runner writes one non-secret canonical memory into the temporary
vault before validation and indexing so recall fixture promotion can be tested
without relying on user data or the distribution checkout's memory files.

## Benefits

- Catches packaging regressions for newer v2 commands.
- Exercises the review-first recall quality loop from an installed CLI.
- Keeps CI behavior aligned with the documented package install path.
- Uses only temporary local vault data and avoids network or external services.

## Limitations

- The smoke still does not publish to TestPyPI or PyPI.
- It does not run a real GUI MCP client.
- The recall fixture promotion case is synthetic; real weekly recall misses
  still require human review.
- The install smoke is slower as more command surfaces are covered.

## Future Risks

- If the package command surface keeps growing, the smoke runner may need
  profile flags for fast versus exhaustive install checks.
- Synthetic fixture data can drift from real-world recall misses unless weekly
  reviewed misses continue to feed `quality/recall-fixtures.json`.
