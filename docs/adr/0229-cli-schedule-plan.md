# ADR 0229: CLI Schedule Plan

## Status

Accepted

## Context

The scheduler implementation already had a review-first contract: package,
Docker, and plugin installation must not create recurring jobs. MCP
`memory.schedule_plan` returned structured platform commands, Docker command
shapes, cron export entries, and side-effect flags, but the equivalent CLI
setup path was split across `schedule setup --dry-run`, `schedule cron --json`,
and `schedule doctor --json`.

That made local setup less consistent for users who install the package with
`pipx` or `uv`, and it encouraged plugin or script authors to parse dry-run
command output instead of consuming one stable JSON contract.

## Decision

Add `ai-dememory schedule plan --json` as a read-only structured scheduler
planning command.

The plan includes:

- normalized daily and weekly schedule values;
- target platform, mode, Docker image, and root;
- platform scheduler commands for install, status, or remove previews;
- daily and weekly cron export entries for install plans;
- explicit side-effect flags:
  `mutates_system=false`, `runs_commands=false`, `writes_files=false`, and
  `installs_schedules=false`; and
- next-action guidance for human review.

MCP `memory.schedule_plan` reuses the same planner so CLI and MCP setup flows
share one contract. `schedule setup --dry-run` remains available for
shell-ready command previews, and `schedule setup` remains the explicit
mutating install path.

## Consequences

- Package users get a single JSON command for scheduler review before any host
  scheduler mutation.
- Plugin skills can prefer structured planning over parsing dry-run text.
- Install smoke now covers the structured scheduler plan.
- MCP and CLI schedule planning stay aligned through one implementation.

## Limitations

- The plan does not query the host scheduler or prove that a timer is installed.
- It does not install or remove systemd timers, Task Scheduler tasks,
  LaunchAgents, or crontab entries.
- Cron entries are still review-only text; the user owns any crontab edit.
- Environment availability remains a separate `schedule doctor --json` check.

## Future Work

- Add signed or externally attributed scheduler acceptance evidence if schedule
  installation becomes a release claim.
- Consider adding richer platform notes if clients gain a setup UI for
  rendering plans.
- Keep remote scheduler orchestration out of scope unless remote deployment is
  explicitly approved.

## Dependencies

- ADR 0026 defines Docker-backed maintenance schedule planning.
- ADR 0028 defines cron export without automatic crontab writes.
- ADR 0066 defines read-only MCP scheduler status.
- ADR 0133 defines scheduler and plugin boundaries.
- ADR 0134 defines MCP schedule-plan cron entries.
- ADR 0142 defines scheduler input validation.

## References

- `scripts/schedule_memory.py`
- `mcp/server/memory_mcp.py`
- `scripts/install_smoke.py`
- `docs/scheduler.md`
- `docs/codex-plugin.md`
