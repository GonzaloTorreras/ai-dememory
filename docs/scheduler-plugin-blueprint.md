# Scheduler And Plugin Blueprint

This blueprint defines the v2 implementation boundary for recurring local
maintenance and the Codex plugin surface.

## Scheduler Contract

Package, Docker image, and plugin installation remain passive. They may install
files that let a user run `ai-dememory`, but they must not install recurring
jobs, read provider chat folders, import conversations, or promote memory.

Recurring work is owned by the host scheduler:

- Windows: Task Scheduler.
- Linux and WSL: user systemd timers when available.
- macOS: LaunchAgents.
- Minimal hosts: reviewed cron export.

`ai-dememory schedule plan --json` is the first structured scheduler review
step for every install. It returns the exact platform commands, run commands,
reviewed cron export entries, and side-effect flags without writing scheduler
config or running host scheduler commands. `ai-dememory schedule setup
--dry-run` remains the command-preview compatibility path.
`ai-dememory schedule cron` prints crontab lines only; it never edits a
crontab.
MCP `memory.schedule_plan` returns the same reviewed cron export entries with
`mutates_system=false` so plugin users can preview minimal-host scheduling
without shelling out to install anything.

Docker mode is local execution, not hosting. The host scheduler still triggers
the job, and the command bind-mounts the selected vault at `/memory` with
`AI_DEMEMORY_ROOT=/memory`.

## Maintenance Profiles

Daily maintenance is for fast local hygiene:

- import enabled provider files as reviewed inbox candidates
- run secret scan before indexing
- rebuild `indexes/memory.sqlite`
- refresh `indexes/memory-graph.json`
- recalculate `indexes/memory-weights.json`
- refresh lifecycle artifacts
- summarize false-positive, conflict, and advisory review recommendation queues
- write a generated maintenance report

Weekly maintenance includes the daily profile and adds slower review tasks:

- consolidation dry-run report
- generated sleep consolidation report
- hook capture review report
- recall fixture evaluation
- maintenance report cleanup

Neither profile promotes durable memory or edits canonical Markdown outside
review-only generated receipts.

## Plugin Shape

The Codex plugin is a workflow bundle around the installed CLI:

- `.codex-plugin/plugin.json` describes the plugin.
- `.mcp.json` launches `ai-dememory mcp --stdio`.
- `hooks/hooks.json` captures small session-event metadata.
- skills guide setup, recall, working sessions, inbox review, and maintenance.

The plugin MCP allowlist is review-first. It includes read-only planning tools
such as `memory.setup_plan`, `memory.schedule_plan`, `memory.schedule_status`,
`memory.setup_health`, `memory.hook_config`, and `memory.providers_plan`, plus
prompt-gated review receipt tools that write only to approved inbox or receipt
locations.
Broader execution and generated-artifact tools are server-only in the default
plugin config: `memory.reindex`, `memory.consolidate`, `memory.secret_scan`,
`memory.mark_seen`, `memory.import_chats`, `memory.maintenance_run`, and
`memory.sleep_apply_reviewed`. Plugin skills should preview with read-only
status or plan tools, then ask the user to run explicit CLI commands when those
actions are intended.

The plugin does not enable unattended maintenance runs by default. A user may
run CLI maintenance directly or install reviewed host scheduler jobs after
inspecting the dry-run output.

## Hook Boundaries

Codex and Claude hooks are session metadata capture points, not schedulers.
Supported events are `UserPromptSubmit`, `PreCompact`, `PostCompact`, and
`Stop`. Hooks write metadata under `inbox/session-events/` by default.

Hooks must not:

- run daily or weekly maintenance
- import provider chat folders
- capture raw payloads unless explicitly configured
- promote inbox candidates
- edit durable memory

## Setup Flow

Recommended local setup:

1. Install the CLI with `pipx install ai-dememory` or
   `uv tool install ai-dememory`.
2. Create or select a private vault with `ai-dememory init <vault>`.
3. Run `ai-dememory setup plan --json`.
4. Run `ai-dememory setup health --json`.
5. Generate MCP config for the chosen client.
6. Preview hooks with `ai-dememory hooks install --client all --dry-run`.
7. Preview maintenance with `ai-dememory schedule plan --json`, then use
   `ai-dememory schedule setup --dry-run` or reviewed cron export from the
   setup-plan `schedule_cron` commands when a human wants shell-ready output.
8. Install only the reviewed hook or schedule pieces the user wants.

MCP clients should use `memory.setup_plan` and `memory.setup_health` for this
flow. Both tools are read-only and report explicit side-effect flags so plugin
skills can explain which follow-up commands write files or mutate host
scheduler state.

## Guardrails

Release checks must keep this blueprint, `docs/scheduler.md`,
`docs/hooks.md`, `docs/codex-plugin.md`, the plugin manifest, plugin MCP config,
plugin hooks, and plugin skills aligned.

When the scheduler or plugin surface changes, update the ADR, release checklist,
and relevant smoke tests in the same PR.
