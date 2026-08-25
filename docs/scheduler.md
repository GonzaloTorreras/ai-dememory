# Scheduler And Maintenance

`ai-dememory` supports opt-in local maintenance. Package installation is
passive: `pip install`, `pipx install`, `uv tool install`, and plugin install do
not create cron jobs, Task Scheduler tasks, systemd timers, or launchd agents.

The implementation contract for scheduler ownership, Docker mode, Codex plugin
skills, and hook boundaries is defined in
[scheduler-plugin-blueprint.md](scheduler-plugin-blueprint.md).

**Docker boundary:** normal users should use the installed CLI in this guide.
Building `ai-dememory:local` runs a trusted checkout and is therefore limited
to explicitly labelled maintainer diagnostics below.

## Maintenance Profiles

Daily maintenance:

```bash
ai-dememory --root <vault-path> maintenance run --profile daily --dry-run --json
ai-dememory --root <vault-path> maintenance run --profile daily
ai-dememory --root <vault-path> maintenance run --profile daily --report-dir reports/maintenance
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
ai-dememory --root <vault-path> maintenance run --profile weekly
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
ai-dememory --root <vault-path> providers plan --json
ai-dememory --root <vault-path> providers configure codex --path "$HOME/.codex" --dry-run --json
ai-dememory --root <vault-path> providers configure codex --path "$HOME/.codex"
ai-dememory --root <vault-path> providers configure claude --path "$HOME/.claude"
ai-dememory --root <vault-path> import-chats codex
```

`providers detect` is a rootless, read-only local diagnostic. The remaining
provider commands require an absolute vault binding. Imports write review
candidates to `inbox/imports/<provider>/`. Secret-like files are skipped. Use
`ai-dememory --root <vault-path> providers configure <provider> --path <path>
--dry-run --json` to review the selected folder before writing
`.ai-dememory.toml`; it does not read provider chat files or write import
candidates. Unchanged provider files that already
have a matching inbox candidate are skipped with reason `already imported`, so
recurring maintenance does not create duplicate review candidates for the same
source path and text. Review and rewrite candidates before promoting any fact
into canonical memory. If a bounded traversal is truncated and a later run sees
only already imported files inside the same window, the result reports
`coverage_blocked=true` plus a bounded `suggested_scan_entries`/next action
instead of claiming complete coverage.

## Install A Schedule

Every `schedule` action except `doctor` must resolve one vault through the
normal runtime order: an explicit `--root`, `AI_DEMEMORY_ROOT`, then the local
default selected with `ai-dememory vault use <absolute-vault-path>`. It never
discovers a vault from the current working directory. The short commands below
assume the setup wizard or `vault use` already saved that default; use
`ai-dememory --root <vault-path> schedule ...` when you want an explicit
one-command override. `schedule doctor` only inspects command availability and
therefore remains rootless.

Preview the commands first:

```bash
ai-dememory schedule plan --json
ai-dememory schedule plan --intensity minimal --json
ai-dememory schedule setup --dry-run
```

### Maintainer-only Docker schedule diagnostics

This subsection is for a contributor or CI/release maintainer validating a
trusted checkout. It assumes an exact local image already exists for that
diagnostic. It is not a user installation, scheduler setup, or fallback for the
installed CLI:

```bash
IMAGE_ID="$(docker image inspect --format '{{.Id}}' ai-dememory:local)"
ai-dememory schedule plan --json \
  --mode docker \
  --image "$IMAGE_ID"
ai-dememory schedule setup --dry-run \
  --mode docker \
  --image "$IMAGE_ID"
```

Unattended Docker schedules accept only immutable
`sha256:<64-hex-image-id>` or `repository@sha256:<64-hex-digest>` references.
The plan reports `docker_image_immutable` and `installable`; a mutable tag has
no `apply_command` or cron export and cannot be installed.
It also reports `resource_policy_valid` and `validation_errors`. An invalid or
out-of-range resource override makes the plan non-installable, suppresses
install commands, cron entries, and `apply_command`, and must be fixed before
autonomous work can be installed. Apply resolves the policy again before
command generation and immediately before any scheduler definition is written.

Install the exact reviewed plan:

```bash
ai-dememory schedule setup \
  --intensity balanced \
  --expect-plan-sha256 <plan_sha256>
```

Inspect or remove:

```bash
ai-dememory schedule status
ai-dememory schedule doctor --json
ai-dememory maintenance status
ai-dememory schedule remove
```

Each vault receives a stable task namespace derived from its path identity, so
multiple vaults do not share global `ai-dememory-daily`/`weekly` task names.
Definitions are created exclusively: Windows does not use forced task
replacement, and systemd/launchd files do not overwrite existing files. The
install transaction reads back the created host definitions and persists their
SHA-256 values with resolved vault root, exact command, versioned plan
projection, namespace, selected profiles, platform, intensity, timestamps, and
plan fingerprint. Apply recomputes that projection and rejects any drift. A
failed write, command, readback, or receipt commit removes the new jobs,
restores files, and does not leave enabled config. `schedule status` refreshes
`verified_at` only when current definitions exactly match that receipt;
host-state verification expires after five minutes. If a vault has moved,
status/removal reports the move and continues to address the original receipt
namespace for host commands and systemd/launchd definition files, so it does
not orphan old jobs. The receipted cadence and intensity remain authoritative
for status and complete removal if resource-policy defaults change later.
If the original path still holds the same enabled receipt, the new path is a
copy rather than an unambiguous move and removal fails closed. Remove from the
original vault first; a future explicit transfer flow can reassign ownership.
Removal first performs the same
comparison, refuses partial profile selection, and restores already removed
jobs if a later removal fails. Windows rollback recreates the exact captured
task XML, not an approximation of the task.

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
`installs_schedules=false`. It also returns `task_namespace`, `intensity`,
`plan_sha256`, and an exact `apply_command`. Use it in plugin or scripted setup
before asking a user to run the mutating command. Docker plans additionally
return `docker_image_immutable` and `installable`. CLI and MCP plans also return
`resource_policy_valid` plus `validation_errors`, so an invalid local policy is
diagnosable without attempting installation.

MCP clients can inspect schedule setup with `memory.schedule_status`. The tool
returns persisted schedule settings, receipt validity, host verification state,
platform status commands, and the compact maintenance `review_due` summary. It
does not install or remove scheduler state. The CLI `schedule status` executes
the platform checks, hashes current definitions, compares the exact receipt,
and clears stale verification evidence on mismatch. If persisted
schedule config contains an invalid time or weekly day, the status response
reports `valid=false` with validation errors and returns no platform status
commands while still reporting pending review work.

MCP clients can call `memory.schedule_plan` to preview the installed-CLI
schedule and equivalent reviewed cron export entries. Its Docker-specific plan
fields are for the maintainer-only diagnostic above; they do not make a local
image a normal user route. The tool is read-only and returns
`mutates_system=false`.
Use `ai-dememory schedule doctor --json` or MCP `memory.schedule_environment`
to check whether scheduler, Docker, and optional crontab commands are discoverable
without running them.

Export crontab lines for Linux, WSL, or minimal hosts without user systemd
timers:

```bash
ai-dememory schedule cron
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
- The maintainer-only Docker validation path still uses the host scheduler; its
  generated daily and weekly commands bind-mount the vault and set
  `AI_DEMEMORY_ROOT=/memory`.

Resource intensities:

| Intensity | Default cadence | Import candidates/run | Timeout | Docker CPU / memory / PIDs |
| --- | --- | ---: | ---: | --- |
| `minimal` | weekly | 5 | 120 s | 0.5 / 256 MiB / 64 |
| `balanced` | daily + weekly | 20 | 300 s | 1.0 / 512 MiB / 128 |
| `active` | daily + weekly | 50 | 900 s | 2.0 / 1 GiB / 256 |

Maintenance subprocesses run in owned process groups/trees. Deadlines terminate
and reap descendants, including grandchildren; Git receives closed stdin and a
non-interactive environment. Windows uses a kill-on-close Job Object and POSIX
uses a new session/process group. Installed mode guarantees tree cleanup and
wall-clock deadlines, not native host CPU/memory quotas. The maintainer-only
Docker validation path additionally enforces the table's CPU, memory, and PID
caps and uses `--network none`; no intensity enables runtime model calls,
embeddings, or durable auto-promotion.

For maintainer-only checkout validation, Docker scheduled jobs use the same
profiles as the installed CLI:

```bash
docker run --rm \
  --network none \
  --cpus 1.0 \
  --memory 512m \
  --pids-limit 128 \
  -e AI_DEMEMORY_ROOT=/memory \
  -v "$PWD:/memory" \
  "$IMAGE_ID" \
  --root /memory maintenance run --profile daily
```

## Hook Capture

Codex plugin hooks can call:

```bash
ai-dememory hook-event --root ~/code/my-memory --event UserPromptSubmit
ai-dememory hook-event --root ~/code/my-memory --event PreCompact
ai-dememory hook-event --root ~/code/my-memory --event PostCompact
ai-dememory hook-event --root ~/code/my-memory --event Stop
```

By default, hook capture stores metadata only under `inbox/session-events/`.
Raw payload capture is off unless explicitly enabled with `--capture-raw`.
Repeated hook captures with the same provider, event, and payload fingerprint
reuse the existing inbox file. JSON hook payloads use a canonical sorted-key
fingerprint; non-JSON payloads use raw-text fingerprints.
