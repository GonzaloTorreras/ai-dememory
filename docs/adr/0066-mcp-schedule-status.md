# ADR 0066: MCP Schedule Status

Status: Accepted for the v2 draft.

## Context

The v2 install workflow is local and opt-in. Package, Docker, and plugin
installation must not create cron jobs, Task Scheduler tasks, systemd timers,
or launchd agents automatically. `memory.schedule_plan` already lets MCP
clients preview install, status, and remove commands, while
`maintenance_status` exposes broad maintenance state.

That still leaves MCP/plugin setup workflows without a focused scheduler status
view. They can infer the configured schedule from maintenance status or ask for
status commands through `memory.schedule_plan`, but they cannot fetch a single
read-only payload that says whether scheduler config is present, which mode is
configured, and which platform status commands a reviewer can run manually.

## Decision

Expose `memory.schedule_status` as a read-only MCP tool.

The tool returns:

- `configured`
- `platform`
- `mode`
- `image`
- `schedule`
- `status_commands`
- `mutates_system`

The implementation reads persisted `.ai-dememory.toml` schedule settings and
uses the same schedule command builder as `memory.schedule_plan` with
`action=status`. It does not execute `systemctl`, `schtasks`, `launchctl`, or
Docker. It does not install, remove, or edit scheduler state.

## Benefits

- Gives Codex plugin skills and MCP clients a direct scheduler diagnostics
  payload.
- Keeps scheduler setup review-first by returning commands instead of running
  platform probes.
- Reuses the existing platform command generator, reducing drift between CLI
  schedule behavior and MCP schedule status.
- Makes runtime smoke verify the schedule-status contract independently from
  broader maintenance status.

## Limitations

- The tool reports persisted configuration and command shapes only. It does not
  prove that a host scheduler job is installed, enabled, or currently healthy.
- OS scheduler inspection remains manual because status commands can hang,
  prompt, depend on permissions, or vary across shells and distributions.
- Docker mode status still reports host scheduler commands; Docker remains only
  the maintenance execution mode.

## Future Risks

- If users expect real host scheduler health over MCP, a separate explicit
  probing tool may be needed with timeout, permission, and privacy controls.
- If schedule configuration moves out of `.ai-dememory.toml`, the tool must
  keep its output stable or document a schema version.
- If remote MCP hosting is added later, scheduler status must stay scoped to
  local hosts and avoid exposing remote platform details accidentally.

## Dependencies

- ADR 0026 defines Docker maintenance schedule planning.
- ADR 0028 defines cron export without automatic crontab writes.
- ADR 0055 defines maintenance artifact and schedule visibility.
- `scripts/schedule_memory.py` remains the shared source of scheduler command
  generation.
