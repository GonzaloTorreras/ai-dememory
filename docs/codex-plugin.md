# Codex Plugin

The repository includes a local Codex plugin scaffold under
`plugins/ai-dememory/` and a repo marketplace at
`.agents/plugins/marketplace.json`.

The plugin bundles skills for setup, recall, inbox review, and maintenance,
MCP configuration for the installed `ai-dememory` CLI, and optional lifecycle
hooks for small session-event metadata capture.

The plugin does not replace the Python package. Install the package first:

```bash
pipx install ai-dememory
# or
uv tool install ai-dememory
```

Then initialize or select a vault:

```bash
ai-dememory init ~/code/my-memory
cd ~/code/my-memory
ai-dememory doctor
```

The scheduler/plugin implementation boundary is documented in
[scheduler-plugin-blueprint.md](scheduler-plugin-blueprint.md). Plugin install
is passive: recurring maintenance, provider imports, and hook installation stay
explicit opt-in actions.

## Bundled MCP Server

The plugin MCP config launches:

```bash
ai-dememory mcp --stdio
```

Smoke test the checked-in plugin config from a source checkout with the
installed CLI:

```bash
python3 scripts/ai_dememory.py mcp-client-smoke \
  --config plugins/ai-dememory/.mcp.json \
  --command ai-dememory
```

Without an installed CLI, override the plugin launch command to the local script:

```powershell
py -3 scripts\ai_dememory.py mcp-client-smoke --config plugins\ai-dememory\.mcp.json --command py --command-arg -3 --command-arg scripts\ai_dememory.py
```

The checked-in plugin defaults to the seven-tool `core` profile:

- `memory.search`
- `memory.get`
- `memory.context`
- `memory.graph`
- `memory.doctor`
- `memory.working_current`
- `memory.working_status`

This keeps model-visible schemas smaller than the recalled context budget. See
[MCP tool profiles](mcp-tool-profiles.md) for the additive `working`, `review`,
and explicit `admin` profiles.

The broader review/admin server inventory remains available for clients that
opt in:

- `memory.search`
- `memory.get`
- `memory.context`
- `memory.graph`
- `memory.doctor`
- `memory.validate_status`
- `memory.write_proposal`
- `memory.capture_miss`
- `memory.recall_miss_candidate`
- `memory.recall_fixture_status`
- `memory.recall_review_plan`
- `memory.recall_review_packet`
- `memory.recall_review_packet_archive_status`
- `memory.recall_review_packet_archive_retention_plan`
- `memory.recall_miss_review`
- `memory.vector_status`
- `memory.roadmap_status`
- `memory.outcome`
- `memory.lifecycle_scores`
- `memory.sleep_plan`
- `memory.working_current`
- `memory.working_status`
- `memory.working_snapshot`
- `memory.working_handoff`
- `memory.maintenance_status`
- `memory.providers_detect`
- `memory.providers_status`
- `memory.providers_plan`
- `memory.setup_plan`
- `memory.setup_health`
- `memory.capture_import`
- `memory.git_lessons`
- `memory.schedule_plan`
- `memory.schedule_status`
- `memory.schedule_environment`
- `memory.provenance_status`
- `memory.acceptance_status`
- `memory.acceptance_verify`
- `memory.acceptance_plan`
- `memory.acceptance_template`
- `memory.acceptance_packet`
- `memory.acceptance_packet_archive_status`
- `memory.acceptance_packet_archive_retention_plan`
- `memory.release_evidence`
- `memory.release_evidence_report`
- `memory.publish_plan`
- `memory.hook_events`
- `memory.hook_config`
- `memory.hook_status`
- `memory.hook_capture_review`
- `memory.review_false_positives`
- `memory.review_stale_false_positives`
- `memory.false_positive_ignore`
- `memory.false_positive_unignore`
- `memory.review_conflicts`
- `memory.conflict_dismiss`
- `memory.conflict_keep`
- `memory.conflict_merge_proposal`
- `memory.review_modes`
- `memory.review_configure_mode`
- `memory.review_plan`
- `memory.review_recommendation`
- `memory.review_recommendations`
- `memory.review_recommendation_archive_status`
- `memory.review_recommendation_archive_restore_preview`
- `memory.review_recommendation_outcome_report`
- `memory.review_recommendation_outcome`

## Server-only MCP tools

Every tool outside `core` is server-only by default. The following broad local
execution tools are available only through the unfiltered `admin` profile or
their explicit CLI equivalents (they are not added by `working` or `review`):

- `memory.reindex`
- `memory.consolidate`
- `memory.secret_scan`
- `memory.mark_seen`
- `memory.import_chats`
- `memory.maintenance_run`
- `memory.sleep_apply_reviewed`

These tools remain available to direct MCP clients that opt into the full server
surface, and to the CLI equivalents. The plugin `core` defaults keep them server-only
because they either run broader local checks, rebuild generated artifacts, read
configured provider sources, record lifecycle telemetry, or apply reviewed
packets. Plugin setup and maintenance skills should use read-only planning and
status tools first, then ask the user to run the explicit CLI command when a
real import, maintenance pass, reindex, or reviewed apply step is intended.

False-positive and conflict receipt tools can accept `recommendation_id` to link
human-approved outcomes back to advisory recommendation artifacts without
editing canonical memory.

## Skills

`memory-setup` handles vault, MCP, provider, hook, and scheduler setup. It can
use read-only `memory.setup_plan` for one structured first-run checklist and
`memory.setup_health` for combined context config, manual acceptance, recall
quality, vector readiness, provider, scheduler, maintenance preflight, artifact,
generated packet archive cleanup, and review status before running any command
that writes files or installs host scheduler state. The setup plan also
includes reviewed cron export commands plus
`generated_reports` commands for optional recall review, recall review packet,
manual acceptance, hook capture review, and release evidence handoff artifacts;
the MCP tool does not write those reports. `generated_archive_status` commands
list generated packet archives without writing files. `generated_archive_retention`
commands preview generated packet cleanup candidates without deleting files.

`memory-recall` tells Codex how to use context, search, get, graph, and current
working-state tools.

`memory-working-session` tells Codex how to read generated current task state,
write working snapshots, and leave handoffs without promoting durable memory.

`memory-review-inbox` keeps imports, hook captures, proposals, recall misses,
git lessons, false positives, review modes, conflict dismissals, keep decisions,
and conflict merge proposals review-first. `memory.git_lessons` lets the plugin
preview local git lesson candidates and only writes to `inbox/git-lessons/` when
`dry_run=false`.
Hook capture review outcomes can be recorded through either
`ai-dememory hooks review` or approval-gated MCP `memory.hook_capture_review`;
both update only selected `inbox/session-events/` candidates and return
`canonical_memory_updated=false`.
Archival of resolved hook captures remains CLI-only through
`ai-dememory hooks archive`; preview it before applying moves to
`archive/session-events/`.
Archival of accepted or rejected review recommendation artifacts is also
CLI-only through `ai-dememory review recommendations-archive`; preview it
before applying moves to `archive/review-recommendations/`.
Before archival, generate the offline outcome sign-off packet with
`ai-dememory review recommendation-outcomes --json`; it writes only under
`reports/` and does not apply review decisions. Use `--limit`, `--offset`, and
`--invalid-offset` to page large active recommendation outcome queues before
archival; MCP `memory.review_recommendation_outcome_report` supports the same
pagination fields without writing files.
Archived recommendation history is read-only through
`ai-dememory review recommendations-archive-status` or
`memory.review_recommendation_archive_status`, with pagination for both valid
records and malformed archive artifacts plus recursive scans for partitioned
archive directories.
Reopening one archived recommendation artifact is CLI-only through
`ai-dememory review recommendations-archive-restore --id <rec_id>`; preview it
before adding `--apply` to move the artifact back to the active inbox.

`memory-maintenance` runs or inspects daily/weekly maintenance, generated
artifact state, generated packet archive cleanup counts, scheduler state, hook
capture review state, advisory review recommendation queue state, and sleep
consolidation plans. It should use `memory.maintenance_status`,
`memory.schedule_plan`, and `memory.setup_health` for plugin-default inspection.
For an actual maintenance pass, the skill should ask the user to run
`ai-dememory maintenance run --profile daily --dry-run` first, then the
explicit non-dry-run CLI command only after review.

Scheduler planning can target either the installed CLI or the local Docker
image. The MCP `memory.schedule_plan` tool is read-only and returns the OS
scheduler commands plus the daily/weekly `run_command`, for example with
`mode=docker` and `image=ai-dememory:local`. It also returns reviewed
`cron_entries` for hosts where user systemd timers are unavailable.
The matching CLI command is `ai-dememory schedule plan --json`; plugin setup
skills should prefer it over parsing `schedule setup --dry-run` output when
they need a structured local preview outside MCP.
`memory.schedule_status` is also read-only. It returns the persisted scheduler
settings, compact `review_due` summary, and the platform status commands a
reviewer can run, but it does not query or mutate the host scheduler. Invalid
persisted scheduler config is reported with `valid=false`, validation errors,
and no platform status commands.
`memory.schedule_environment` checks target scheduler, Docker, and optional
crontab command availability without running those commands. `memory.hook_status`
reports whether managed Codex or Claude hook instruction blocks are installed
without writing files, and includes a frontmatter-only summary of
`inbox/session-events/` capture candidates, including due review counts. It can
scope capture summaries with `capture_provider`, `capture_event`, and
`capture_review_status` when the inbox is large, plus
`capture_created_from`/`capture_created_to` and
`capture_review_after_from`/`capture_review_after_to` date windows.

Provider setup diagnostics can use `memory.providers_detect` to find likely
local folders, `memory.providers_status` to see which configured providers are
enabled and import-ready, and `memory.providers_plan` to return reviewable
configure/import command arrays for the user's chosen paths. The plan includes
`configure_dry_run_command` so setup can preview the selected folder before
writing `.ai-dememory.toml`, and `import_dry_run_command` so setup can preview
provider imports before writing inbox candidates.
`memory.providers_status` and `memory.providers_plan` do not read provider chat
files or write import candidates.

Generated working state can be handled through `memory.working_current`,
`memory.working_status`, `memory.working_snapshot`, and
`memory.working_handoff`. Snapshot and handoff writes are secret-scanned and
stay under `working/`; they are not durable memory promotion.

Release readiness can be inspected through read-only MCP tools:
`memory.provenance_status` audits durable review metadata,
`memory.acceptance_status` summarizes reviewed manual acceptance evidence, and
`memory.acceptance_verify` returns whether all manual items have passing
evidence. `memory.acceptance_plan` lists the remaining or blocked manual checks,
the reviewed CLI commands to record the result, and `suggested_artifacts` for
the proof a reviewer should attach. `memory.acceptance_template` returns a
single-item evidence template without recording proof. Both tools accept
optional `reviewer` and `pr_url` metadata to pre-fill generated record commands
without recording evidence.
`memory.acceptance_packet` renders the full review packet without writing a
report or recording proof; use `limit` and `offset` to page incomplete review
items, and pass `reviewer` or `pr_url` when a release handoff should carry that
context. `memory.acceptance_packet_archive_status` lists generated packet
snapshots without writing files or recording proof.
`memory.acceptance_packet_archive_retention_plan` previews generated packet
archive cleanup candidates without deleting files or recording proof.
`memory.release_evidence` returns the read-only release evidence, including
`release_blockers`, when the MCP root is the
distribution checkout; `memory.release_evidence_report` renders the same
Markdown handoff without writing reports. Both release-evidence tools accept
optional `reviewer` and `pr_url` metadata to pre-fill manual acceptance plans
and handoff command arrays without recording proof. `memory.publish_plan`
returns the manual TestPyPI/PyPI workflow dispatch plan, preflight command
arrays, release blockers, target-specific `publish_ready`, final
`release_ready`, required PR URL dispatch input, and false side-effect flags
without uploading packages. Plain vaults get unavailable release evidence
inside the publish plan instead of a failed tool call. Evidence recording stays
on the CLI through `ai-dememory acceptance record`.

Recall quality freshness can also be inspected through
`memory.recall_fixture_status`. It reports seed-only or stale fixtures without
capturing misses or editing `quality/recall-fixtures.json`.
`memory.recall_miss_candidate` checks a query and expected memory rank before
writing recall feedback; it is read-only and returns capture commands only when
the query is outside the accepted rank window.
`memory.recall_review_plan` adds pending, malformed, and bounded recent
resolved recall miss review state without promoting misses or editing fixture
files. `memory.recall_review_packet` renders the weekly review packet without
writing reports, fixtures, or miss outcomes; use `limit`, `pending_offset`, and
`invalid_offset` when pending or malformed miss sections are large, and pass
`reviewer` or `pr_url` when a PR handoff should carry that context.
`memory.recall_review_packet_archive_status` lists generated recall packet
snapshots without writing files, fixtures, or miss outcomes.
`memory.recall_review_packet_archive_retention_plan` previews generated recall
packet archive cleanup candidates without deleting files, writing fixtures, or
closing miss files.
`memory.recall_miss_review` records reviewed `rejected` or `dismissed` outcomes on miss files under
`inbox/recall-feedback/` without writing fixtures or canonical memory.

Vector readiness can be inspected through `memory.vector_status`. It reports
whether measured recall failures justify a future vector experiment without
creating embeddings or vector indexes.

Roadmap status can be inspected through `memory.roadmap_status`. It returns the
same read-only implementation phase map as `ai-dememory roadmap status`,
including implemented phases, gated vector-search status, and next actions.

## Hooks

The plugin bundles Codex hooks for `UserPromptSubmit`, `PreCompact`,
`PostCompact`, and `Stop`. Hooks call `ai-dememory hook-event` and store
metadata in `inbox/session-events/`. They do not run weekly maintenance, import
provider folders, or promote durable memory. Repeated hook captures with the
same provider, event, and payload fingerprint reuse the existing inbox file.
JSON hook payloads use canonical sorted-key fingerprints, while non-JSON
payloads use raw-text fingerprints.

Generate provider hook fragments with:

```bash
ai-dememory hooks config --client codex
ai-dememory hooks config --client claude
```

Inspect managed hook instruction status with:

```bash
ai-dememory hooks list --json
```

MCP clients can use read-only `memory.hook_status` for the same setup signal and
to see bounded hook capture counts without reading raw payload bodies. After
human review, they can use approval-gated `memory.hook_capture_review` to close
a selected capture without promoting canonical memory.
For large inboxes, pass `capture_provider`, `capture_event`, or
`capture_review_status` to `memory.hook_status` before choosing a capture to
review. Add `capture_created_from`, `capture_created_to`,
`capture_review_after_from`, or `capture_review_after_to` when review work needs
a date window.

Generate a frontmatter-only review report from the local CLI with:

```bash
ai-dememory hooks captures --write-report
```

The report is written under the vault, path-bounded to the memory root, and
secret-scanned before saving. It contains counts, due paths, malformed
candidates, latest capture metadata, and fingerprints, but not raw payload
text.

After review, close candidates that do not need promotion with:

```bash
ai-dememory hooks review --path inbox/session-events/<capture>.md --status dismissed --reviewed-by "Your Name" --reason "No durable memory needed."
```

MCP clients can record the same receipt with `memory.hook_capture_review` when
the user approves the selected capture, status, reviewer, and reason.
Resolved hook captures can be moved out of the review inbox with the local CLI
`ai-dememory hooks archive --json`, followed by `--apply` only after approval.

Install or remove managed agent instruction blocks with:

```bash
ai-dememory hooks install --client codex
ai-dememory hooks uninstall --client codex
```

See [hooks.md](hooks.md) for Claude Code hook configuration, safety boundaries,
and manual capture examples.

## Local Marketplace

Codex can discover the repo plugin through `.agents/plugins/marketplace.json`.
After installing or refreshing that marketplace, install the `ai-dememory`
plugin from the Codex plugin directory.
