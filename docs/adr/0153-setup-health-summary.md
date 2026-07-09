# ADR 0153: Setup Health Summary

Status: Accepted

## Context

`ai-dememory setup plan` returns reviewable first-run commands, while scheduler
environment diagnostics, persisted schedule status, provider readiness,
generated artifact state, false-positive review due summaries, stale
suppression summaries, and conflict review summaries were split across several
commands and MCP tools.

The next v2 setup UX needs one read-only status response that a CLI user,
plugin skill, or MCP client can inspect before deciding which setup or review
commands to run.

## Decision

Add `ai-dememory setup health --json` and MCP `memory.setup_health`.

The setup health response combines:

- scheduler environment readiness
- persisted scheduler status and validation
- provider readiness
- generated artifact status
- maintenance lock state
- false-positive review due counts
- stale false-positive suppression counts
- conflict review counts
- concrete next actions

The command and MCP tool are passive. They set `mutates_system=false`,
`runs_commands=false`, and `writes_files=false`. They do not install scheduler
jobs, write hook config, configure providers, read provider chat files, write
reports, or promote memory.

## Consequences

- Setup skills can use `memory.setup_health` after `memory.setup_plan` to show
  current local status before applying setup changes.
- Release checks, MCP runtime smoke, plugin config validation, and inventory
  docs now cover the setup health surface.

## Limitations

- Setup health readiness is a local summary. It does not prove that host
  scheduler jobs are installed or working because it does not run `systemctl`,
  `schtasks`, `launchctl`, `crontab`, or Docker commands.

## Future Work

- Add client-specific setup health rendering if Codex, Claude, or other MCP
  clients need different next-action wording.
- Add optional host scheduler verification only as an explicit command that may
  run local status commands.
- Feed reviewed setup health issues into manual acceptance reports if release
  readiness needs a summarized setup section.

## Dependencies

- ADR 0079 defines read-only local setup planning.
- ADR 0136 adds provider readiness to maintenance status.
- ADR 0145 defines scheduler environment diagnostics.
- ADR 0151 adds review due summaries to scheduler status.
- ADR 0152 adds conflict review summaries to maintenance status.
