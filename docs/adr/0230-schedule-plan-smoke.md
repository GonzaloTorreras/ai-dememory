# ADR 0230: Schedule Plan Smoke Coverage

## Status

Accepted

## Context

ADR 0229 added `ai-dememory schedule plan --json` so package, plugin, and MCP
setup flows can review scheduler commands, cron entries, and side-effect flags
without installing host scheduler state. The command was present in install
smoke, but command success alone did not prove the returned JSON preserved the
review-first contract.

Docker smoke also verified doctor, index, maintenance status, release evidence,
MCP stdio, client config, and vault template export behavior, but it did not
exercise scheduler planning from inside the local image.

## Decision

Strengthen install smoke with schedule-plan payload assertions.

Installed package smoke now validates that `schedule plan --json` returns:

- `action=install`;
- the expected vault root;
- daily and weekly scheduler commands;
- daily and weekly cron entries;
- maintenance run commands; and
- `mutates_system=false`, `runs_commands=false`, `writes_files=false`, and
  `installs_schedules=false`.

Docker local smoke now runs `ai-dememory schedule plan --json` inside the
image with the vault bind-mounted at `/memory` and validates the same
side-effect contract with `root=/memory`.

## Consequences

- Package and Docker distribution checks prove the scheduler planning contract,
  not just command availability.
- CI catches regressions that accidentally remove cron entries, run commands,
  or side-effect flags from schedule plans.
- Docker remains local-only; the smoke does not install host scheduler jobs or
  run Docker from inside Docker.

## Limitations

- The smoke does not verify that the host scheduler accepts the generated
  command lines.
- The Docker smoke validates installed-mode planning inside the image, not a
  nested Docker-backed schedule plan.
- Manual acceptance is still required for any real scheduler installation
  claim.

## Future Work

- Add reviewed manual acceptance evidence for one real scheduler install only
  if the release scope starts claiming installed recurring jobs.
- Add platform-specific schedule-plan fixtures if Windows, Linux, and macOS
  command generation diverges further.
- Keep Cloud Build and remote scheduler orchestration deferred until remote
  deployment is explicitly approved.

## Dependencies

- ADR 0011 defines reusable install smoke.
- ADR 0026 defines Docker-backed maintenance schedule planning.
- ADR 0075 defines Docker vault-template export smoke.
- ADR 0127 defines publish workflow smoke gates.
- ADR 0229 defines the CLI schedule-plan command.

## References

- `scripts/install_smoke.py`
- `tests/test_memory_tools.py`
- `docs/release-v2-checklist.md`
- `.github/workflows/ci.yml`
