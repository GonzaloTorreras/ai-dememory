# ADR 0134: MCP Schedule Plan Cron Entries

## Status

Accepted

## Context

The CLI already supports `ai-dememory schedule cron` for Linux, WSL, and
minimal hosts where user systemd timers are unavailable. The MCP
`memory.schedule_plan` tool exposed platform scheduler commands and Docker run
commands, but it did not expose the equivalent cron export lines.

That left Codex plugin setup weaker than the CLI setup path: a plugin user
could preview Task Scheduler, systemd, launchd, or Docker-backed schedule
commands through MCP, but had to leave the MCP flow to inspect reviewed cron
lines.

## Decision

Extend `memory.schedule_plan` with:

- `cron_entries`: daily and weekly reviewed cron export entries for install
  plans
- `mutates_system=false`: an explicit side-effect flag matching setup-plan
  safety language

Cron entries are returned for `action=install` only. Status and remove plans
return an empty `cron_entries` list because the CLI cron path is export-only and
does not own removal or host status checks.

## Consequences

- Codex plugin setup can show minimal-host scheduling options without invoking
  shell commands.
- Docker mode cron entries use the same bind-mounted `/memory` command shape as
  CLI cron export.
- MCP scheduler planning remains read-only and does not install or edit
  crontabs.

## Limitations

- The tool does not detect whether cron is installed or enabled on the host.
- The tool does not write crontab entries or remove existing entries.
- The returned cron lines still require human review before installation.

## Future Work

- Add manual acceptance evidence for one real cron-based install path if cron
  support becomes part of the release claim.
- Consider including platform-specific installation notes if MCP clients gain a
  richer setup UI.
- Keep remote scheduler orchestration out of scope unless remote deployment is
  explicitly approved.

## Dependencies

- ADR 0028 defines cron maintenance export without automatic crontab writes.
- ADR 0066 defines read-only MCP scheduler status.
- ADR 0133 defines the scheduler and plugin implementation blueprint.

## References

- `scripts/schedule_memory.py`
- `mcp/server/memory_mcp.py`
- `docs/scheduler.md`
- `docs/codex-plugin.md`
