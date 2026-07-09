# ADR 0028: Cron Maintenance Export

## Status

Accepted for v2 draft.

## Context

The local scheduler supports Windows Task Scheduler, Linux user systemd timers,
macOS LaunchAgents, and Docker-backed maintenance commands. Some Linux, WSL, or
minimal environments do not have working user systemd timers, but they can still
run recurring maintenance through cron.

Package and plugin installation must remain passive, so cron support should not
write to a user's crontab automatically.

## Decision

Add `ai-dememory schedule cron`.

The command prints reviewed crontab lines for daily and weekly maintenance. It
supports the same installed-CLI and Docker modes as scheduler setup:

- installed CLI: `ai-dememory maintenance run --profile ...`
- Docker: `docker run --rm -e AI_DEMEMORY_ROOT=/memory -v <vault>:/memory
  <image> maintenance run --profile ... --root /memory`

`--json` returns structured entries with the cron schedule, command arguments,
and rendered line. The command never installs the lines.

## Benefits

- Covers Linux/WSL hosts where user systemd timers are unavailable.
- Keeps recurring maintenance setup review-first and explicit.
- Reuses the same daily and weekly maintenance profile commands as other
  scheduler surfaces.
- Provides Docker-compatible cron lines without turning Docker into a remote
  service.

## Limitations

- Users must install the rendered lines themselves with their preferred crontab
  workflow.
- The exporter does not validate the host cron implementation.
- Environment variables, PATH, and Docker availability remain host concerns.
- The cron exporter does not replace systemd/launchd/Task Scheduler integration
  where those are preferred.

## Future Risks

- Some cron implementations require explicit shells or absolute command paths.
- If cron installation is automated later, it will need a separate approval
  flow and backup strategy for existing crontabs.
- Container runtime variants such as Podman may need a runtime option.
