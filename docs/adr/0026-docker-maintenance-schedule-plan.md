# ADR 0026: Docker Maintenance Schedule Plan

## Status

Accepted for v2 draft.

## Context

`ai-dememory` supports a local Docker image for reproducible MCP stdio usage.
The scheduler previously generated installed-CLI maintenance commands only.
Users who prefer Docker still needed to hand-write recurring commands for daily
index, graph, weight, provider import, and weekly recall/consolidation work.

Package and plugin installation must remain passive, so Docker scheduling should
be planned explicitly instead of installed automatically.

## Decision

Extend `ai-dememory schedule` and MCP `memory.schedule_plan` with a
`mode` option:

- `installed` runs `ai-dememory maintenance run ...` from the installed CLI.
- `docker` runs `docker run --rm -e AI_DEMEMORY_ROOT=/memory -v
  <vault>:/memory <image> maintenance run ...`.

Schedule dry-runs and MCP planning now include the underlying `run_command` for
daily and weekly jobs. Linux systemd and macOS launchd files are rendered with
the selected run command when a human explicitly installs the schedule.

## Benefits

- Gives Docker users a reproducible recurring maintenance command.
- Keeps the private vault bind-mounted and separate from the package image.
- Preserves passive package/plugin installation.
- Lets Codex and other MCP clients inspect Docker schedule plans without
  installing OS scheduler state.

## Limitations

- Docker schedules still depend on the host scheduler.
- The Docker image must already be built or available locally.
- Windows Task Scheduler receives the Docker command as a task action string,
  so users should preview with `--dry-run` before installing.
- This does not add remote hosting, Cloud Build, or HTTP MCP scheduling.

## Future Risks

- Podman or alternate container runtimes may need a separate runtime option.
- Linux systems without user systemd timers may still need a crontab exporter.
- Docker Desktop path sharing can block bind mounts until the user enables the
  vault drive or directory.
