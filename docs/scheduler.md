# Scheduler And Maintenance

`ai-dememory` supports opt-in local maintenance. Package installation is
passive: `pip install`, `pipx install`, `uv tool install`, and plugin install do
not create cron jobs, Task Scheduler tasks, systemd timers, or launchd agents.

The implementation contract for scheduler ownership, Docker mode, Codex plugin
skills, and hook boundaries is defined in
[scheduler-plugin-blueprint.md](scheduler-plugin-blueprint.md).

## Maintenance Profiles

Daily maintenance:

```bash
ai-dememory maintenance run --profile daily --dry-run --json
ai-dememory maintenance run --profile daily
ai-dememory maintenance run --profile daily --report-dir reports/maintenance
```

The dry-run previews enabled provider imports and generated artifact targets
without writing inbox files, indexes, reports, or scheduler state. Daily
maintenance imports enabled provider chat/session files into
`inbox/imports/<provider>/`, runs a secret scan before indexing, rebuilds
`indexes/memory.sqlite`, refreshes `indexes/memory-graph.json`, recalculates
`indexes/memory-weights.json`, refreshes lifecycle score artifacts at
`indexes/memory-lifecycle.json` and `reports/lifecycle.md`, and writes a report
under `reports/maintenance/`.
Custom report directories must stay inside the memory root. Rendered
maintenance reports are secret-scanned before writing.

Weekly maintenance:

```bash
ai-dememory maintenance run --profile weekly
```

Weekly maintenance includes the daily tasks and also writes
`reports/consolidation-dry-run.md`, writes the generated sleep consolidation
handoff at `reports/sleep-plan.md`, writes the frontmatter-only
`reports/hook-captures.md` review report, runs recall fixtures when present,
and removes old maintenance reports. Maintenance never promotes inbox
candidates into durable memory.

## Provider Imports

```bash
ai-dememory providers detect
ai-dememory providers plan --json
ai-dememory providers configure codex --path "$HOME/.codex" --dry-run --json
ai-dememory providers configure codex --path "$HOME/.codex"
ai-dememory providers configure claude --path "$HOME/.claude"
ai-dememory import-chats codex
```

Imports write review candidates to `inbox/imports/<provider>/`. Secret-like
files are skipped. Use `providers configure --dry-run --json` to review the
selected folder before writing `.ai-dememory.toml`; it does not read provider
chat files or write import candidates. Unchanged provider files that already
have a matching inbox candidate are skipped with reason `already imported`, so
recurring maintenance does not create duplicate review candidates for the same
source path and text. Review and rewrite candidates before promoting any fact
into canonical memory.

## Install A Schedule

Preview the commands first:

```bash
ai-dememory schedule plan --json
ai-dememory schedule setup --dry-run
```

Preview a Docker-backed schedule when you want recurring maintenance to run
through the local image instead of the installed CLI:

```bash
ai-dememory schedule plan --json \
  --mode docker \
  --image ai-dememory:local
ai-dememory schedule setup --dry-run \
  --mode docker \
  --image ai-dememory:local
```

Install after review:

```bash
ai-dememory schedule setup
```

Inspect or remove:

```bash
ai-dememory schedule status
ai-dememory schedule doctor --json
ai-dememory maintenance status
ai-dememory schedule remove
```

`maintenance status` reports configured providers, provider import readiness
without reading provider files, schedule settings, recent maintenance reports,
false-positive review due counts, stale suppression counts, conflict review
counts, advisory review recommendation queue counts, hook capture review
counts, generated packet archive cleanup counts, lock state, whether generated
index, graph, weight, lifecycle, hook capture report, and sleep plan report
artifacts exist, and a read-only `artifact_freshness` summary that flags
missing or stale generated artifacts relative to canonical memory Markdown. It
does not delete generated packet archives or refresh generated artifacts.

`schedule plan --json` is the structured local planning surface. It returns the
same platform scheduler commands as `schedule setup --dry-run`, includes
reviewed cron export entries for minimal hosts, and reports
`mutates_system=false`, `runs_commands=false`, `writes_files=false`, and
`installs_schedules=false`. Use it in plugin or scripted setup before asking a
user to run the mutating `schedule setup` command.

MCP clients can inspect schedule setup with `memory.schedule_status`. The tool
returns persisted schedule settings, platform status commands, and the compact
maintenance `review_due` summary. It does not run `systemctl`, `schtasks`, or
`launchctl`, and it never installs or removes scheduler state. If persisted
schedule config contains an invalid time or weekly day, the status response
reports `valid=false` with validation errors and returns no platform status
commands while still reporting pending review work.

MCP clients can also call `memory.schedule_plan` to preview installed-CLI or
Docker scheduler commands and the equivalent reviewed cron export entries. The
tool is read-only and returns `mutates_system=false`.
Use `ai-dememory schedule doctor --json` or MCP `memory.schedule_environment`
to check whether scheduler, Docker, and optional crontab commands are discoverable
without running them.

Export crontab lines for Linux, WSL, or minimal hosts without user systemd
timers:

```bash
ai-dememory schedule cron
ai-dememory schedule cron --mode docker --image ai-dememory:local
ai-dememory schedule cron --json
```

`schedule cron` only prints reviewed lines. It never installs or edits a
crontab. Schedule times must use 24-hour `HH:MM`; weekly days must be one of
`SUN`, `MON`, `TUE`, `WED`, `THU`, `FRI`, or `SAT`.

Platform behavior:

- Windows uses Task Scheduler.
- Linux/WSL uses systemd user timers.
- Cron export is available for hosts where user systemd timers are unavailable.
- macOS writes LaunchAgents.
- Docker mode still uses the host scheduler. Generated daily and weekly run
  commands bind-mount the vault and set `AI_DEMEMORY_ROOT=/memory`.

Docker scheduled jobs run the same profiles as the installed CLI:

```bash
docker run --rm \
  -e AI_DEMEMORY_ROOT=/memory \
  -v "$PWD:/memory" \
  ai-dememory:local \
  maintenance run --profile daily --root /memory
```

## Hook Capture

Codex plugin hooks can call:

```bash
ai-dememory hook-event --event UserPromptSubmit
ai-dememory hook-event --event PreCompact
ai-dememory hook-event --event PostCompact
ai-dememory hook-event --event Stop
```

By default, hook capture stores metadata only under `inbox/session-events/`.
Raw payload capture is off unless explicitly enabled with `--capture-raw`.
Repeated hook captures with the same provider, event, and payload fingerprint
reuse the existing inbox file. JSON hook payloads use a canonical sorted-key
fingerprint; non-JSON payloads use raw-text fingerprints.
