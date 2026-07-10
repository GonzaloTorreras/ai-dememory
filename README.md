# ai DeMemory

Personal multi-LLM memory repository for Codex, Claude, Gemini, Obsidian, and
future tools.

Markdown is the canonical source of truth. SQLite FTS, exports, reports, and
future vector indexes are generated from Markdown and can be rebuilt.

## Status

- Current release target: local MCP v2.0 readiness.
- MCP protocol baseline: stable `2025-11-25`, with `2024-11-05` accepted for
  older clients.
- Transport: local MCP stdio plus optional local REST API.
- License: Apache-2.0; use, modification and redistribution are permitted under
  the terms in `LICENSE`.
- Pull request workflow: keep PRs draft until human review is complete.
- Remote HTTP, OAuth, automatic durable writes, and vector search are out of
  scope for this release.

## Quick Start

Install the tool, then create a private memory vault:

```bash
pipx install ai-dememory
ai-dememory init ~/code/my-memory
cd ~/code/my-memory
ai-dememory doctor
```

`uv` users can install the same tool with `uv tool install ai-dememory`.

If you want a reusable private GitHub vault template repo instead of creating a
single local vault, export the packaged vault template:

```bash
ai-dememory vault-template export ~/code/ai-dememory-vault-template
```

Review the exported files, push them to a separate private repository, then mark
that repository as a GitHub template. Keep the tool distribution repo separate
from private memory vault repos.

Before the package is published to PyPI, install from GitHub or a local checkout:

```bash
pipx install git+https://github.com/GonzaloTorreras/ai-dememory.git
```

Run from the repository root. On Windows PowerShell, use `py -3` if `python3`
is not available.

```bash
python3 scripts/ai_dememory.py doctor
python3 scripts/ai_dememory.py validate
python3 scripts/ai_dememory.py validate --json
python3 scripts/ai_dememory.py secret-scan
python3 scripts/ai_dememory.py index
python3 scripts/ai_dememory.py search ai-dememory --limit 3
python3 scripts/ai_dememory.py search ai-dememory --why
python3 scripts/ai_dememory.py context ai-dememory --budget 2000
python3 scripts/ai_dememory.py graph --json
python3 scripts/ai_dememory.py setup plan --json
python3 scripts/ai_dememory.py setup health --json
python3 scripts/ai_dememory.py recall-fixtures packet --limit 50 --pending-offset 50 --invalid-offset 50 --write-report
python3 scripts/ai_dememory.py providers detect
python3 scripts/ai_dememory.py capture markdown --path ./notes.md
python3 scripts/ai_dememory.py maintenance status
python3 scripts/ai_dememory.py schedule plan --json
python3 scripts/ai_dememory.py schedule setup --dry-run
```

`search --why` reports both numeric scoring components and matched evidence
fields such as `matched_terms`, `matched_fields`, `matched_tags`, and
`matched_aliases`. MCP `memory.search` returns the same explanation object.
`context` reads optional `[context]` defaults from `.ai-dememory.toml`;
explicit CLI flags and MCP arguments take precedence. Use `context --why` or
MCP `memory.context` with `explain_results=true` to include ranking evidence in
assembled Markdown context.
`setup plan --json` is read-only and includes `generated_reports` command
arrays for optional recall review, recall review packet, manual acceptance,
manual acceptance packet, hook capture review, and release evidence handoff
artifacts. It also includes `generated_archive_status` command arrays for
read-only recall and manual acceptance packet archive inspection, plus
`generated_archive_retention` command arrays for previewing generated packet
archive cleanup candidates without deleting files.
`setup health --json` is read-only and combines validation status, context
config status, manual acceptance readiness, recall review status, vector
readiness, scheduler environment/status, provider readiness, maintenance
preflight commands, generated artifact state and freshness, generated packet
archive cleanup counts, lock state, and review queues into one local setup
health summary.
`schedule plan --json` is read-only and returns host scheduler commands,
reviewed cron export entries, Docker command shapes when requested, and
side-effect flags before any `schedule setup` command writes config or touches
host scheduler state.
`maintenance status` reports generated artifact state and freshness, generated
packet archive cleanup counts, provider readiness, false-positive review due
counts, stale suppression counts, conflict review counts, and hook capture
review counts without reading provider chat files, deleting archives, or
writing canonical memory.

Optional editable install from a local checkout:

```bash
python3 -m pip install -e .
ai-dememory doctor
ai-dememory search ai-dememory --limit 3
```

Use WSL paths for active Linux/web tooling checkouts when possible, but the
repository tools are dependency-light and also run from native PowerShell.

Package installation is passive. Scheduled maintenance, provider imports, and
Codex or Claude hook capture are explicit opt-in steps.

## Architecture

- Markdown and Obsidian are the human-editable source of truth.
- Private GitHub syncs and versions canonical memory.
- SQLite FTS5 is the local retrieval and ranking layer.
- MCP exposes recall and write proposals to LLM tools.
- A local REST API exposes health, search, graph, reindex, and proposal
  endpoints for scripts and local dashboards that cannot launch MCP stdio.
- Graph generation uses `indexes/memory.sqlite` when available and falls back
  to Markdown parsing when the index is missing.
- Vector search is optional later, only if measured recall failures justify it.

See [docs/architecture.md](docs/architecture.md), [docs/schema.md](docs/schema.md),
[docs/operations.md](docs/operations.md), [docs/mcp-v2.md](docs/mcp-v2.md), and
[docs/mcp-v2-gap-analysis.md](docs/mcp-v2-gap-analysis.md).

Distribution and user vault setup:

- Install guide: [docs/install.md](docs/install.md)
- Local MCP server setup: [docs/local-mcp.md](docs/local-mcp.md)
- Local REST API: [docs/local-api.md](docs/local-api.md)
- Memory graph: [docs/memory-graph.md](docs/memory-graph.md)
- Memory quality: [docs/memory-quality.md](docs/memory-quality.md)
- Future master plan: [PLAN.md](PLAN.md)
- Shared memory governance roadmap:
  [docs/shared-memory-governance-roadmap.md](docs/shared-memory-governance-roadmap.md)
- Import and capture: [docs/import-capture.md](docs/import-capture.md)
- Git lesson capture: [docs/git-lessons.md](docs/git-lessons.md)
- Future vector migration: [docs/vector-migration.md](docs/vector-migration.md)
- Operational loop: [docs/operational-loop.md](docs/operational-loop.md)
- Review workflows: [docs/review-workflows.md](docs/review-workflows.md)
- Sleep consolidation: [docs/sleep-consolidation.md](docs/sleep-consolidation.md)
- Scheduler and maintenance: [docs/scheduler.md](docs/scheduler.md)
- Scheduler/plugin blueprint: [docs/scheduler-plugin-blueprint.md](docs/scheduler-plugin-blueprint.md)
- Local hook integrations: [docs/hooks.md](docs/hooks.md)
- Codex plugin: [docs/codex-plugin.md](docs/codex-plugin.md)
- Distribution plan: [docs/distribution.md](docs/distribution.md)
- Create a memory repo: [docs/create-memory-repo.md](docs/create-memory-repo.md)
- GitHub vault template source: [vault-template/](vault-template/)

## Safety Model

- Never store secrets, tokens, private keys, service-account JSON, cookies,
  recovery codes, or `.env` contents.
- Durable memories require human review before modification.
- LLMs may write proposals to `inbox/llm-captures/`, not directly to durable
  memory.
- Generated indexes live under `indexes/` and can be rebuilt.
- Secret scanning and schema validation run before indexing.
- `sensitivity: secret-prohibited` is reserved for quarantined material and is
  rejected from canonical memory.
- `private` and `sensitive` memories are excluded from default search/MCP
  results and generated LLM context unless explicitly included by a local user.

## Repository Layout

- `memories/durable/`: reviewed durable values, preferences, policies, and facts.
- `memories/active/`: short-lived current working context.
- `memories/projects/`: project-specific memories and decisions.
- `memories/tools/`: tool-specific setup and behavior notes.
- `inbox/`: LLM proposals and raw captures awaiting human review.
- `inbox/imports/`: provider chat/session import candidates.
- `inbox/git-lessons/`: git history lesson candidates.
- `inbox/session-events/`: optional Codex/Claude hook metadata candidates.
- `inbox/conflict-resolution/`: reviewed conflict merge proposals.
- `inbox/review-recommendations/`: advisory LLM/client review recommendation
  artifacts that still require human action.
- `inbox/sleep-consolidation/`: generated sleep review packets.
- `working/`: generated current task state and handoffs.
- `indexes/`: generated SQLite and future vector indexes.
- `distilled/`: generated session context exports.
- `reports/`: generated review, scan, and consolidation reports.
- `mcp/`: MCP server skeleton and integration notes.
- `scripts/`: validation, scanning, indexing, search, export, and review tools.
- `templates/`: Obsidian-friendly memory templates.

## MCP v2 Operation

- Client config examples: [docs/mcp-client-config.md](docs/mcp-client-config.md)
- Protocol gap analysis: [docs/mcp-v2-gap-analysis.md](docs/mcp-v2-gap-analysis.md)
- v2 release checklist: [docs/release-v2-checklist.md](docs/release-v2-checklist.md)
- PR-gated MCP runtime smoke: `python3 scripts/ai_dememory.py mcp-smoke`
- PR handoff: [docs/pr-draft.md](docs/pr-draft.md)
- Roadmap status: [docs/roadmap-status.md](docs/roadmap-status.md)
- Future master plan: [PLAN.md](PLAN.md)
- Shared-memory governance roadmap:
  [docs/shared-memory-governance-roadmap.md](docs/shared-memory-governance-roadmap.md)

Implemented MCP surface: 74 MCP tools.

- Tools: `memory.search`, `memory.get`, `memory.write_proposal`,
  `memory.mark_seen`, `memory.reindex`, `memory.consolidate`,
  `memory.secret_scan`, `memory.graph`, `memory.doctor`,
  `memory.validate_status`, `memory.capture_miss`,
  `memory.recall_miss_candidate`,
  `memory.recall_fixture_status`, `memory.recall_review_plan`,
  `memory.recall_review_packet`,
  `memory.recall_review_packet_archive_status`,
  `memory.recall_review_packet_archive_retention_plan`,
  `memory.recall_miss_review`,
  `memory.vector_status`, `memory.roadmap_status`, `memory.context`,
  `memory.outcome`, `memory.lifecycle_scores`, `memory.maintenance_status`, `memory.import_chats`,
  `memory.capture_import`, `memory.git_lessons`, `memory.maintenance_run`, `memory.schedule_plan`,
  `memory.schedule_status`, `memory.schedule_environment`, `memory.hook_events`,
  `memory.hook_config`, `memory.hook_status`, `memory.hook_capture_review`, `memory.sleep_plan`,
  `memory.sleep_apply_reviewed`, and
  `memory.working_current`, `memory.working_status`,
  `memory.working_snapshot`, `memory.working_handoff`,
  `memory.providers_detect`, `memory.providers_status`,
  `memory.providers_plan`, `memory.setup_plan`, `memory.setup_health`,
  `memory.review_false_positives`,
  `memory.review_stale_false_positives`,
  `memory.false_positive_ignore`, `memory.false_positive_unignore`,
  `memory.review_conflicts`,
  `memory.conflict_dismiss`, `memory.conflict_keep`,
  `memory.conflict_merge_proposal`,
  `memory.review_modes`, `memory.review_configure_mode`,
  `memory.review_plan`, `memory.review_recommendation`,
  `memory.review_recommendations`,
  `memory.review_recommendation_archive_status`,
  `memory.review_recommendation_archive_restore_preview`,
  `memory.review_recommendation_outcome_report`,
  `memory.review_recommendation_outcome`,
  `memory.provenance_status`,
  `memory.acceptance_status`, `memory.acceptance_verify`,
  `memory.acceptance_plan`, `memory.acceptance_template`,
  `memory.acceptance_packet`,
  `memory.acceptance_packet_archive_status`,
  `memory.acceptance_packet_archive_retention_plan`,
  `memory.release_evidence`,
  `memory.release_evidence_report`, and
  `memory.publish_plan`.
- Resources: `memory://id/{id}` and `memory://path/{path}` for public/internal
  canonical memories.
- Prompts: `memory_recall_context`, `memory_capture_proposal`,
  `memory_review_inbox`.
- Utilities: `initialize`, `notifications/initialized`, and `ping`.

The checked-in Codex plugin enables a curated review-first subset of the MCP
server. `memory.reindex`, `memory.consolidate`, `memory.secret_scan`,
`memory.mark_seen`, `memory.import_chats`, `memory.maintenance_run`, and
`memory.sleep_apply_reviewed` are server-only by default for plugin installs;
use the CLI or an explicitly broader MCP client config when those broad local
actions are intended.

Safety defaults:

- MCP resources never expose `private`, `sensitive`, or `secret-prohibited`
  memories by default.
- Tools that can include sensitive content require an explicit
  `include_sensitive` argument.
- `memory.write_proposal` writes only to `inbox/llm-captures/` and scans the
  rendered Markdown before writing.
- Working-memory tools write only generated operational state under `working/`;
  they do not promote durable memories.
- `memory.secret_scan` only accepts repository-relative paths through MCP.
- Review write tools only update `.ai-dememory-ignore.toml` or
  `inbox/conflict-resolution/`; false-positive suppressions report derived
  `review_due` and `review_after_status` fields from their `review_after`
  dates.
- Recall miss review writes only update reviewed frontmatter on files under
  `inbox/recall-feedback/`; fixture promotion remains a separate CLI review
  action.
- `memory.mark_seen` and `memory.outcome` return structured lifecycle receipts;
  outcome receipts report counters and metadata without echoing feedback notes.
- Docker is supported only for local stdio MCP usage with a bind-mounted vault;
  no ports or remote service are exposed.

## Local REST API

Run a loopback-only API for local scripts and dashboards:

```bash
python3 scripts/ai_dememory.py api --host 127.0.0.1 --port 8765
```

Endpoints include `/health`, `/search`, `/memories/{id}`, `/graph`,
`/proposals`, and `/reindex`. Non-loopback binds require `AI_DEMEMORY_API_KEY`
or an explicit unsafe override. See [docs/local-api.md](docs/local-api.md).

## Workflow

1. Capture new information as Markdown in `inbox/` or the appropriate
   `memories/` folder.
2. Run validation and secret scanning.
3. Rebuild the SQLite index.
4. Search or export context for LLM sessions.
5. Promote inbox proposals to durable/project/active memories only after review.

## Validation And Release Gates

Run from the repository root:

```bash
python3 scripts/ai_dememory.py doctor
python3 scripts/ai_dememory.py verify-mcp
python3 scripts/ai_dememory.py ci-guard
python3 scripts/ai_dememory.py artifact-guard
python3 scripts/ai_dememory.py vault-setup-guard
python3 scripts/ai_dememory.py pr-template-guard
python3 scripts/ai_dememory.py pr-draft-guard
python3 scripts/ai_dememory.py acceptance-guard
python3 scripts/ai_dememory.py adr-guard
python3 scripts/ai_dememory.py release-checklist-guard
python3 scripts/ai_dememory.py release-check
python3 scripts/ai_dememory.py roadmap status --json
python3 scripts/ai_dememory.py api-smoke
python3 scripts/ai_dememory.py validate
python3 scripts/ai_dememory.py validate --json
python3 scripts/ai_dememory.py secret-scan
python3 scripts/ai_dememory.py eval-recall
python3 scripts/ai_dememory.py recall-fixtures status --json
python3 scripts/ai_dememory.py recall-fixtures review-plan --json
python3 scripts/ai_dememory.py recall-fixtures review-plan --write-report
python3 scripts/ai_dememory.py recall-fixtures packet --write-report
python3 scripts/ai_dememory.py recall-fixtures promote-miss --help
python3 scripts/ai_dememory.py recall-fixtures review-miss --help
python3 -m unittest discover -s tests
python3 -m compileall -q scripts mcp/server ai_dememory_tool
```

CI runs `artifact-guard` before release gates and runs
`package-build-smoke --check-clean` after install, package-build, and Docker
smoke commands so stale package build metadata cannot be left behind by
validation.

After a draft PR exists, run the runtime MCP smoke with the PR URL set:

```bash
AI_DEMEMORY_PR_URL="https://github.com/GonzaloTorreras/ai-dememory/pull/<number>" python3 scripts/ai_dememory.py release-check --strict
AI_DEMEMORY_PR_URL="https://github.com/GonzaloTorreras/ai-dememory/pull/<number>" python3 scripts/ai_dememory.py mcp-smoke
```

PowerShell equivalent:

```powershell
$env:AI_DEMEMORY_PR_URL = "https://github.com/GonzaloTorreras/ai-dememory/pull/<number>"
py -3 scripts\ai_dememory.py release-check --strict
py -3 scripts\ai_dememory.py mcp-smoke
```

Generated artifact smoke commands:

```bash
python3 scripts/ai_dememory.py index
python3 scripts/ai_dememory.py search codex
python3 scripts/ai_dememory.py graph
python3 scripts/ai_dememory.py maintenance run --profile daily --dry-run --json
python3 scripts/ai_dememory.py maintenance run --profile daily
python3 scripts/ai_dememory.py maintenance run --profile weekly --dry-run --json
python3 scripts/ai_dememory.py maintenance run --profile weekly
python3 scripts/ai_dememory.py lifecycle scores --json
python3 scripts/ai_dememory.py lifecycle report
python3 scripts/ai_dememory.py sleep plan
python3 scripts/ai_dememory.py sleep --dry-run --json
python3 scripts/ai_dememory.py sleep --propose --id sleep_... --json
python3 scripts/ai_dememory.py sleep --apply-reviewed --id sleep_... --json
python3 scripts/ai_dememory.py sleep apply-reviewed --all
python3 scripts/ai_dememory.py working status --json
python3 scripts/ai_dememory.py hooks config --client codex
python3 scripts/ai_dememory.py hooks config --client claude
python3 scripts/ai_dememory.py hooks captures --json
python3 scripts/ai_dememory.py hooks captures --provider codex --review-status pending --json
python3 scripts/ai_dememory.py hooks captures --created-from 2026-06-01 --created-to 2026-06-30 --json
python3 scripts/ai_dememory.py hooks captures --write-report
python3 scripts/ai_dememory.py hooks review --help
python3 scripts/ai_dememory.py hooks archive --json
python3 scripts/ai_dememory.py hooks install --client all --dry-run
python3 scripts/ai_dememory.py providers configure codex --path "$HOME/.codex" --dry-run --json
python3 scripts/ai_dememory.py schedule plan --json
python3 scripts/ai_dememory.py schedule plan --json --mode docker --image ai-dememory:local
python3 scripts/ai_dememory.py schedule setup --dry-run --mode docker --image ai-dememory:local
python3 scripts/ai_dememory.py schedule cron --json
python3 scripts/ai_dememory.py schedule doctor --json
python3 scripts/ai_dememory.py export-context
python3 scripts/ai_dememory.py consolidate --dry-run
python3 scripts/ai_dememory.py review false-positives
python3 scripts/ai_dememory.py review false-positives --due-only
python3 scripts/ai_dememory.py review stale-false-positives
python3 scripts/ai_dememory.py review conflicts
python3 scripts/ai_dememory.py review modes
python3 scripts/ai_dememory.py review plan --kind conflict
python3 scripts/ai_dememory.py review recommendation --kind conflict --target-id conf_example --recommendation collect_evidence --rationale "Needs human review." --recommended-by "Local LLM" --json
python3 scripts/ai_dememory.py review recommendations --json
python3 scripts/ai_dememory.py review recommendation-outcome --id rec_example --status accepted --reviewer "You" --reason "Reviewed." --json
python3 scripts/ai_dememory.py review recommendation-outcomes --json
python3 scripts/ai_dememory.py review recommendation-outcomes --limit 50 --offset 50 --invalid-offset 50 --json
python3 scripts/ai_dememory.py conflict resolve --id conf_example --keep mem_example --recommendation-id rec_example --reviewer "You"
python3 scripts/ai_dememory.py review recommendations-archive-status --limit 50 --offset 50 --invalid-offset 50 --json
python3 scripts/ai_dememory.py capture text --stdin --title "Session lesson"
python3 scripts/ai_dememory.py learn --git --days 7 --repo .
python3 scripts/ai_dememory.py learn --git --days 7 --repo . --write
python3 scripts/ai_dememory.py vector status
python3 scripts/ai_dememory.py recall-fixtures status --strict --max-age-days 14
python3 scripts/ai_dememory.py recall-fixtures review-plan
python3 scripts/ai_dememory.py recall-fixtures review-plan --write-report
python3 scripts/ai_dememory.py recall-fixtures packet --write-report
python3 scripts/ai_dememory.py recall-fixtures promote-miss --help
python3 scripts/ai_dememory.py recall-fixtures review-miss --help
python3 scripts/ai_dememory.py acceptance status
python3 scripts/ai_dememory.py acceptance plan
python3 scripts/ai_dememory.py acceptance plan --write-report
python3 scripts/ai_dememory.py acceptance packet --write-report
python3 scripts/ai_dememory.py acceptance packet --limit 50 --offset 50 --write-report
```

`review modes` and `review plan` include normalized `[false_positives]` and
`[conflicts]` policy values from `.ai-dememory.toml`, including
`triage_policy`, `resolution_policy`, scan toggles, and LLM auto-deny
categories. These settings are exposed as review guidance; durable and
canonical memory writes remain explicitly review-gated.
Setting `[false_positives].enabled = false` or `[conflicts].enabled = false`
makes the corresponding review reports and MCP listing tools return no
candidates, and blocks review-state write commands for that workflow.
JSON and MCP review listing responses include `enabled` and `policy` metadata
for the relevant workflow. Generated Markdown review reports include the same
compact `Review Policy` section, so archived false-positive, stale-suppression,
and conflict reports show whether a workflow was disabled or simply empty.
When `[conflicts].scan_on_validate = true`, `validate` also reports a
non-blocking conflict review scan summary after frontmatter validation succeeds.
When `[conflicts].scan_on_consolidate = true`, `consolidate --dry-run` includes
the same non-blocking conflict review evidence in its generated report.

False-positive suppressions use `[false_positives].review_after_days` from
`.ai-dememory.toml` when `--review-after-days` is omitted. New vaults default
to 90 days, and explicit CLI/MCP arguments still override that policy per
reviewed finding. Review state defaults to `.ai-dememory-ignore.toml`, or to
`[false_positives].ignore_file` when configured inside the vault.
Conflict reports and merge proposals use `[conflicts].report_path` and
`[conflicts].proposal_path` when no explicit report path is supplied; both paths
are constrained to the vault.

Product acceptance stays separate from automated package gates. This repository
is AI-operated and human-account-owned: Codex maintains release PRs, versions,
changelog entries, merges and tags; green CI creates the immutable version tag;
the canonical release workflow builds once, smokes the exact wheel and sdist,
attests them, publishes through OIDC and verifies the installed index package.
See `docs/ai-operated-releases.md`.

Manual acceptance remains useful for product and vault behavior, but it does
not authorize or block package publication. After a reviewer uses a real MCP
client, inspects an Obsidian vault, reviews a provider import, or verifies
another checklist item, record that separate product evidence with:

```bash
ai-dememory acceptance record \
  --item mcp-client-installed \
  --reviewed-by "Reviewer Name" \
  --summary "Generated config was used with a real MCP client."
ai-dememory acceptance verify
ai-dememory release-evidence --write-report
ai-dememory release-evidence --strict
python scripts/ai_release_guard.py --version-only --json
```

`publish-plan` is read-only. It resolves `workflow_url` from project repository
metadata first, falls back to the local GitHub remote when available, and keeps
a placeholder in plain vaults or non-GitHub checkouts. It reports both final
`release_ready` and target-specific `publish_ready`. TestPyPI `publish_ready`
can defer only the `testpypi-publish` acceptance item because that evidence is
created by the TestPyPI workflow; all other blockers still prevent dispatch.
PyPI `publish_ready` requires full `release_ready` after TestPyPI evidence is
recorded. The publish workflow requires a PR URL and sets
`AI_DEMEMORY_PR_URL` from that input before strict publish planning.

Use `ai-dememory release-evidence --write-report --report-path
reports/v2-release-evidence.md` when a handoff needs an explicit generated
report target. The path must stay inside the memory root and the rendered
Markdown is secret-scanned before writing.
Add `--reviewer "Reviewer Name"` or set `AI_DEMEMORY_REVIEWER` when release
evidence should pre-fill reviewer identity in embedded manual acceptance plans,
templates, packets, and strict handoff commands. Add `--pr-url https://github.com/...`
or set `AI_DEMEMORY_PR_URL` to carry the pull request URL into the same
read-only handoff guidance. These fields do not record acceptance evidence.

Use `ai-dememory acceptance plan` to see remaining or blocked manual checks and
the reviewed-evidence commands to run after each check. Each plan item also
includes `suggested_artifacts`, such as a client log, reviewed inbox path,
maintenance report, or TestPyPI workflow URL, so reviewers know what proof to
attach before recording acceptance.
Use `ai-dememory acceptance plan --write-report` to write the same read-only
plan to `reports/manual-acceptance-plan.md` for handoffs. That generated report
does not record evidence or count as acceptance; reviewers still need to run
`ai-dememory acceptance record` with real proof.
Use `ai-dememory acceptance packet --write-report` to write
`reports/manual-acceptance-packet.md`, a reviewer-facing packet with fill-in
sections, suggested artifacts, and pass/block record commands for every
incomplete manual acceptance item. Use `--limit` and `--offset` to page large
incomplete-item sections. Add `--reviewer "Reviewer Name"` and `--pr-url
https://github.com/...` when a PR handoff should pre-fill reviewer and pull
request context in the packet header. Add `--archive` when a review needs a
timestamped copy under `reports/manual-acceptance-packets/`. It is still not
evidence. Use `ai-dememory acceptance packet-archive-status --json` to list
those generated packet snapshots with pagination metadata; the status command
does not write files or record acceptance evidence. Use
`ai-dememory acceptance packet-archive-retention-plan --json` to preview
cleanup candidates after keeping the newest 30 generated packet snapshots by
default; the retention plan does not delete files.
Use `ai-dememory acceptance template --item <item-id>` when a reviewer needs a
single-item evidence template without recording proof. The template is
read-only guidance until `ai-dememory acceptance record` is run with reviewed
details.
Both `acceptance plan` and `acceptance template` accept
`--reviewer "Reviewer Name"` and `--pr-url https://github.com/...` to pre-fill
generated record commands with a reviewer and PR artifact while still leaving
the item-specific summary for human review.
`ai-dememory release-evidence --json` and the Markdown report also embed this
manual acceptance plan so final handoffs include example record commands,
suggested artifacts, and not only the remaining item descriptions.
They also include `release_blockers`, a structured summary of dirty worktree,
automated warning/failure, recall quality, and manual acceptance blockers that
currently keep `release_ready` false. Recall freshness remains visible through
`recall_fixture_freshness` and `recall_fixture_review_plan`; stale seed-only
fixtures become a `recall_fixture_review` blocker only when there are pending
or invalid recall miss files, recall eval is unavailable, or the current eval
has failures. A clean current eval with no miss files stays visible as review
evidence but does not force a synthetic miss before package release.
Release evidence also includes `vector_readiness`, the same measured recall gate
used by `ai-dememory vector status`, with `creates_embeddings=false`. If recall
fixtures make a vector experiment eligible, `release_blockers` adds
`vector_readiness_review` so the release handoff requires review before any
embedding dependency or privacy model is approved.
The same output includes a top-level `next_actions` list plus compact
`setup_health_summary` and `maintenance_summary` objects so final handoffs show
the ordered work remaining alongside validation, context
defaults, scheduler readiness, hook capture review due counts, provider import
readiness, recall review, vector readiness, generated artifact state and
freshness, review queue counts, generated packet archive cleanup counts, and
setup next actions without recording evidence, installing hooks, deleting
archives, refreshing generated artifacts, or running maintenance commands.
It also includes `handoff_commands`: copyable command arrays for writing release
evidence, generating manual acceptance and recall review packets, running
strict release evidence, verifying manual acceptance, checking recall freshness,
planning TestPyPI/PyPI publishes, and running the publish guard. These commands
are guidance; reviewers still need real evidence before recording acceptance or
publishing.
The handoff payload separates `payload_*` side-effect flags from
`command_side_effects`; constructing release evidence remains read-only, while
commands such as `--write-report` are explicitly marked as writing generated
files and publish-plan commands are marked as running local read-only
inspection if reviewers choose to run them.
When reviewer and PR URL metadata are provided to `release-evidence`, the
embedded `acceptance_plan` and `acceptance_template` handoff commands include
that metadata so reviewers can copy the generated commands without replacing
placeholders first.
Weekly maintenance writes `reports/sleep-plan.md` as generated compaction
review evidence; it does not write sleep review packets or mutate canonical
memory.
Use `ai-dememory recall-fixtures check-miss --query "<query>" --expected-id
<memory-id> --json` before writing recall feedback. The check is read-only and
reports whether the expected memory is outside the accepted rank window plus
the exact `capture-miss --dry-run` and write commands to run if the miss is
real.
Use `ai-dememory recall-fixtures packet --write-report` when the weekly recall
review needs a reviewer-facing handoff with fill-in fields, promote/reject
commands, and final `eval-recall` and `release-evidence --strict` reminders.
Add `--reviewer "Reviewer Name"` and `--pr-url https://github.com/...` when a
PR handoff should pre-fill reviewer and pull request context in the packet
header. Add `--archive` when the weekly quality review needs a timestamped copy
under `reports/recall-review-packets/`. The packet is generated guidance only;
it does not promote fixtures, close miss files, or write
`quality/recall-fixtures.json`. Use
`ai-dememory recall-fixtures packet-archive-status --json` to list generated
recall packet snapshots with pagination metadata; the status command is
read-only and does not promote fixtures. Use
`ai-dememory recall-fixtures packet-archive-retention-plan --json` to preview
cleanup candidates after keeping the newest 30 generated packet snapshots by
default; the retention plan does not delete files.

If a manual check was attempted but cannot pass on the current workstation,
record it as blocked instead of leaving the attempt invisible:

```bash
ai-dememory acceptance record \
  --item mcp-client-docker \
  --status blocked \
  --reviewed-by "Reviewer Name" \
  --summary "Docker is unavailable on this workstation."
```

Blocked records appear in `release-evidence`, but the item remains incomplete
until a later `passed` record exists. `ai-dememory acceptance verify` exits
nonzero until every manual acceptance item has reviewed passing evidence.
`ai-dememory release-evidence --strict` also exits nonzero until automated
evidence is clean and manual acceptance is complete.

Acceptance evidence is written under `inbox/release-acceptance/` and
secret-scanned before it is saved.

Direct script entry points remain available when debugging an individual tool:

```bash
python3 scripts/validate_memory.py
python3 scripts/validate_memory.py --json
python3 scripts/secret_scan.py
python3 scripts/index_memory.py
python3 scripts/search_memory.py codex
python3 scripts/export_context.py
python3 scripts/consolidate_memory.py --dry-run
```

## MCP Server

Run as a stdio MCP server:

```bash
python3 scripts/ai_dememory.py mcp --stdio
```

PowerShell direct smoke examples:

```powershell
'{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{}}}' | py -3 scripts\ai_dememory.py mcp --stdio
'{"jsonrpc":"2.0","id":2,"method":"ping"}' | py -3 scripts\ai_dememory.py mcp --stdio
```

Do not expose the stdio server as a network service without a separate
authentication and authorization design.

## CI

GitHub Actions runs compile, schema validation, secret scan, static MCP contract
verification, release readiness, PR-gated strict release readiness and MCP
runtime smoke on pull requests, unit tests, index rebuild, search smoke, package
install smoke, package build smoke, Docker local MCP smoke, and the final
package build artifact clean check. The PR-gated checks receive
`AI_DEMEMORY_PR_URL` from the pull request event, and runtime smoke exercises a
live stdio server process.
The ordinary release readiness check runs before index generation; the strict
PR-only release readiness check runs after index/search/recall smoke so doctor
has generated index evidence.

## Generated Artifacts

Generated artifacts must be reproducible from Markdown. SQLite databases,
context exports, and reports are not canonical memory unless a human explicitly
reviews and promotes their content into `memories/`. Before release, run
`ai-dememory artifact-guard` or `python3 scripts/ai_dememory.py artifact-guard`
to confirm generated outputs are not staged.
