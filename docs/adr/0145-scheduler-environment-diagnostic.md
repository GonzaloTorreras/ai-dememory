# ADR 0145: Scheduler Environment Diagnostic

## Status

Accepted

## Context

The v2 scheduler flow is intentionally review-first. Users can preview host
scheduler commands, Docker-backed run commands, and cron exports without
installing anything. ADR 0144 made invalid scheduler config visible through MCP,
but users still lacked a read-only way to distinguish configuration problems
from missing local executables such as `systemctl`, `schtasks`, `launchctl`,
`docker`, or `crontab`.

Running those platform commands inside a diagnostic would blur the safety
boundary because some commands query host scheduler state and others may not be
available in CI or minimal containers.

## Decision

Add a read-only scheduler environment diagnostic:

- CLI: `ai-dememory schedule doctor --json`
- MCP: `memory.schedule_environment`

The diagnostic uses command discovery only. It checks whether the target
platform scheduler command is present, whether Docker is present when
`mode=docker`, and whether `crontab` is available as an optional helper for
installing reviewed cron exports.

The diagnostic reports `mutates_system=false` and `runs_commands=false`.

## Consequences

- Setup and plugin workflows can explain missing local prerequisites without
  running host scheduler commands.
- Docker-backed scheduling can fail readiness when Docker is required but not
  available.
- Cron remains a reviewed export path; `crontab` availability is reported as
  optional rather than required.

## Limitations

- Command discovery does not prove the current user can successfully use the
  scheduler or Docker.
- It does not inspect running timers, Task Scheduler jobs, LaunchAgents, Docker
  daemon state, or image availability.
- Cross-platform checks report command availability for the current machine,
  not a remote target.

## Future Work

- Add optional deeper diagnostics if users explicitly request host scheduler or
  Docker execution checks.
- Consider adding image-existence checks for Docker mode, still behind an
  explicit non-mutating probe.
- Keep scheduler installation and removal in CLI-only explicit commands.

## Dependencies

- ADR 0066 defines read-only MCP scheduler status.
- ADR 0133 defines scheduler and plugin setup boundaries.
- ADR 0142 defines scheduler input validation.
- ADR 0144 defines MCP scheduler validation fields.

## References

- `scripts/schedule_memory.py`
- `mcp/server/memory_mcp.py`
- `docs/scheduler.md`
