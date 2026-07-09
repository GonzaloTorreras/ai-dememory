# ADR 0135: Setup Plan Cron Export Commands

## Status

Accepted

## Context

`ai-dememory setup plan --json` is the read-only first-run checklist used by
CLI users and MCP plugin setup flows. It already returned scheduler dry-run
commands for installed and Docker-backed maintenance, but it did not return the
reviewed cron export commands.

After `memory.schedule_plan` gained `cron_entries`, this left the higher-level
setup plan incomplete for Linux, WSL, and minimal hosts where user systemd
timers are unavailable.

## Decision

Add two command arrays to the setup plan:

- `schedule_cron`: `ai-dememory schedule cron`
- `docker_schedule_cron`: `ai-dememory schedule cron --mode docker --image <image>`

The setup plan remains passive. These arrays are instructions for review; the
setup planner does not run them, edit crontabs, install hooks, install
schedules, read provider files, or write import candidates.

## Consequences

- Codex plugin setup can present scheduler dry-runs and minimal-host cron
  export paths from one MCP `memory.setup_plan` response.
- Installed CLI and Docker maintenance scheduling have symmetric first-run
  guidance.
- Release checklist and runtime smoke now catch drift if these command arrays
  disappear.

## Limitations

- The setup plan does not validate that cron exists on the host.
- The setup plan does not know which scheduler path the user will choose.
- Human review is still required before installing any generated cron lines.

## Future Work

- If manual acceptance later includes a real cron install, record it as
  reviewed evidence instead of treating setup-plan output as proof.
- If scheduler profiles become configurable, include the configured daily and
  weekly times in setup-plan cron command examples.
- If remote hosting is added, keep these commands scoped to local vault
  maintenance only.

## Dependencies

- ADR 0028 defines cron maintenance export.
- ADR 0079 defines read-only local setup planning.
- ADR 0134 defines MCP schedule-plan cron entries.

## References

- `scripts/setup_plan.py`
- `scripts/schedule_memory.py`
- `mcp/server/memory_mcp.py`
