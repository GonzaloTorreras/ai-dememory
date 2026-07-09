# Memory MCP Server

`memory_mcp.py` is the local-first MCP server for personal memory. It exposes
tools, resources, and prompts over stdio JSON-RPC, while keeping Markdown as the
canonical source of truth.

Implemented capabilities:

- `tools`: 74 MCP tools covering search, get, write proposal, mark seen, reindex, consolidate dry-run,
  secret scan, context assembly, outcome feedback, graph, recall-miss capture,
  doctor readiness checks, validation status, recall fixture freshness, review packets, and review outcomes, vector readiness, durable provenance audits,
  working memory status, snapshots, and handoffs, lifecycle scores, provider
  detection/status/setup-plan/import, git lesson capture, maintenance status/run
  with generated artifact state/freshness and generated packet archive status,
  setup planning/health, schedule planning/status, roadmap status, release evidence, reports, publish planning, manual acceptance readiness, planning, templates, and packets, sleep consolidation packets, review
  mode planning, false-positive review, and conflict review/proposal tools.
- `resources`: list and read public/internal memory documents as
  `memory://id/{id}` resources.
- `prompts`: recall context, capture proposal, and inbox review prompt
  templates.
- `ping`: connection-health checks return an empty result.

The server targets MCP protocol `2025-11-25` and still accepts `2024-11-05` for
older clients.

Validate tool definitions:

```bash
python3 mcp/server/memory_mcp.py --list-tools
python3 scripts/mcp_inventory.py --check-docs
```

Call a tool directly from Bash/WSL:

```bash
python3 mcp/server/memory_mcp.py --call memory.search --args '{"query":"codex","limit":3}'
```

Search results include the same `why` object as `ai-dememory search --why`,
including numeric score components plus `matched_terms`, `matched_fields`,
`matched_tags`, and `matched_aliases`.

From PowerShell, prefer stdio JSON-RPC to avoid native argv quote rewriting:

```powershell
'{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"memory.search","arguments":{"query":"codex","limit":3}}}' | py -3 mcp\server\memory_mcp.py --stdio
```

Run as a stdio JSON-RPC server:

```bash
python3 mcp/server/memory_mcp.py --stdio
```

List resources:

```powershell
'{"jsonrpc":"2.0","id":2,"method":"resources/list"}' | py -3 mcp\server\memory_mcp.py --stdio
```

List prompts:

```powershell
'{"jsonrpc":"2.0","id":3,"method":"prompts/list"}' | py -3 mcp\server\memory_mcp.py --stdio
```

`memory.write_proposal` pre-scans rendered proposal text, then writes only to
`inbox/llm-captures/`. It does not promote or overwrite durable memory.

`memory.capture_miss` writes only to `inbox/recall-feedback/`.

`memory.recall_miss_candidate` checks a query plus expected memory id or path
against current ranked search results without writing files. It returns the
expected rank, top results, `candidate_miss`, and capture commands only when
the query is outside the accepted rank window.

`memory.doctor` returns the same local readiness checks, selected profile, and
status counts as the CLI doctor without mutating files. Vault roots skip
distribution-only MCP contract checks.

`memory.validate_status` returns the same structured status as
`ai-dememory validate --json`, including frontmatter errors, memory count, and
conflict scan policy state. It is read-only and does not write reports, review
state, or canonical memory.

`memory.recall_fixture_status` reports whether recall fixtures are seed-only,
stale, or fresh based on reviewed miss promotions. It is read-only and does not
modify `quality/recall-fixtures.json`.

`memory.recall_review_plan` reports fixture freshness plus pending, malformed,
bounded recent resolved `inbox/recall-feedback/` miss files, and a
`candidate_check_command` template to run before new capture. It is read-only,
redacts secret-like fields, and does not promote misses or edit
`quality/recall-fixtures.json`.

`memory.recall_review_packet` renders the weekly recall review packet without
writing `reports/recall-review-packet.md`, fixture files, or miss outcomes.
`limit`, `pending_offset`, and `invalid_offset` page pending and malformed miss
sections. Optional `reviewer` and `pr_url` arguments pre-fill handoff metadata
in the packet header.

`memory.recall_review_packet_archive_status` lists generated recall packet
snapshots without writing files, fixtures, or miss outcomes. `limit` and
`offset` page generated archive entries.
`memory.recall_review_packet_archive_retention_plan` previews generated recall
packet archive cleanup candidates after keeping the newest `keep` snapshots.
It is read-only and does not delete files, write fixtures, or close miss files.

`memory.recall_miss_review` records a reviewed `rejected` or `dismissed`
outcome on a recall miss under `inbox/recall-feedback/`. It secret-scans the
review metadata, returns an audit receipt, and does not write fixture files or
canonical memory.

`memory.vector_status` reports whether measured recall failures justify a
future vector-search experiment. It is read-only and does not create embeddings
or vector indexes.

`memory.provenance_status` audits durable memories for `reviewed: true`,
`reviewed_by`, and `reviewed_at` metadata. It is read-only and does not write a
report file.

`memory.working_current`, `memory.working_status`, `memory.working_snapshot`,
and `memory.working_handoff` expose generated current task state and handoffs
under `working/`. Snapshot and handoff writes are secret-scanned and do not
mutate canonical memory.

`memory.context` returns a token-budgeted context bundle and excludes restricted
memory by default. It accepts either an explicit `query` or `auto: true` to
derive the query from generated working memory, and returns `query_source` so
clients can display where the query came from. Omitted `budget_tokens`,
`include_working_memory`, and `explain_results` arguments use the vault-local
`[context]` defaults from `.ai-dememory.toml`.

`memory.mark_seen` records retrieval usage in generated SQLite tables and
returns a structured receipt containing the query, selected memory id, score,
caller, timestamp, and whether lifecycle state was updated.

`memory.outcome` records good/bad usefulness feedback in the generated lifecycle
tables and returns a structured receipt containing the selected memory id,
target source, updated positive/negative counters, strength, reward factor,
timestamp, and whether lifecycle state was updated. It does not mutate Markdown
memory or echo outcome notes.

`memory.lifecycle_scores` returns generated lifecycle scoring data derived from
retrieval and outcome feedback.

`memory.import_chats` writes only to `inbox/imports/<provider>/`; imported
content remains a review candidate. With `dry_run=true`, it reads and scans
provider files, returns `would_write`, and writes no inbox files. Repeated
provider candidates with the same stable fingerprint are skipped with reason
`already imported`.

`memory.git_lessons` inspects local git history and previews review-first lesson
candidates by default. It defaults to `dry_run=true`; callers must set
`dry_run=false` before writing inbox candidates to `inbox/git-lessons/`. It never
promotes durable memory. Repeated candidates with the same stable fingerprint
are skipped with reason `already captured`.

`memory.providers_status` reports configured, enabled, and import-ready
provider paths without reading provider chat files or writing import
candidates.

`memory.providers_plan` returns reviewable `providers configure`,
`import-chats --dry-run --json`, and `import-chats` command arrays for each
known provider. It is read-only, does not configure providers, does not read
provider chat files, and does not write import candidates.

`memory.maintenance_status` returns schedule settings, provider config,
provider import readiness, false-positive review due counts, stale suppression
counts, conflict review counts, advisory review recommendation counts, hook
capture review counts, generated packet archive cleanup counts, recent reports,
lock state, and generated artifact state/freshness. It is read-only and does
not read provider chat files, write import candidates, refresh artifacts, delete
archives, apply review recommendations, or mutate canonical memory.

`memory.maintenance_run` runs an opt-in daily or weekly profile. With
`dry_run=true`, it previews enabled provider imports and generated artifact
targets without writing files, rebuilding indexes, or creating inbox
candidates. Dry-runs report that generated packet archives are reviewed but not
deleted. Weekly previews include the generated hook capture report target.

`memory.setup_plan` returns reviewable first-run setup command arrays for
doctor, index, graph, MCP config, provider planning, hook config, scheduler
dry-run, maintenance, and acceptance planning. It is read-only and does not
write files, install hooks, install schedules, read provider files, or write
import candidates.

`memory.setup_health` returns combined validation status, context config status,
manual acceptance readiness, recall review status, scheduler environment/status,
vector readiness, hook instruction status, provider readiness, maintenance
preflight commands and artifact targets, generated artifact state, lock state,
generated packet archive cleanup counts, false-positive review due summary,
stale suppression summary, and conflict review summary. It is read-only, does
not run commands, does not read provider files, does not write files, and does
not delete archives.

`memory.schedule_plan` returns installed-CLI or Docker scheduler commands,
including daily/weekly `run_command` details and reviewed cron export entries,
but does not install them.

`memory.schedule_status` returns persisted schedule settings, the compact
maintenance `review_due` summary, and the platform-specific status commands. It
does not execute `systemctl`, `schtasks`, or `launchctl`, and it does not
install, remove, or edit scheduler state.
Its output schema includes `valid` and `validation_errors`; invalid persisted
scheduler config returns no platform status commands.
`memory.schedule_environment` checks command availability for the target host
scheduler, Docker mode, and optional crontab installation without executing
those commands.
`memory.hook_status` returns managed Codex/Claude hook instruction status and a
bounded frontmatter-only hook capture summary, including review outcome counts
and review-after due state, without writing files or reading raw payload
bodies. Optional `capture_provider`, `capture_event`, and
`capture_review_status` filters scope the capture summary for high-volume
review queues. Date-window filters `capture_created_from`,
`capture_created_to`, `capture_review_after_from`, and
`capture_review_after_to` further bound frontmatter-only review queues.
`memory.hook_capture_review` records approval-gated review receipts on selected
`inbox/session-events/` captures and returns `canonical_memory_updated=false`;
it does not promote durable memory or delete capture files.

`memory.acceptance_status`, `memory.acceptance_verify`,
`memory.acceptance_plan`, `memory.acceptance_template`, and
`memory.acceptance_packet` are read-only release readiness helpers.
`memory.acceptance_packet_archive_status` is a read-only generated archive
browser. They inspect reviewed manual acceptance records, next actions,
single-item evidence templates, the full review packet, and generated packet
archive metadata but do not record evidence or write reports.
`memory.acceptance_packet` accepts `limit` and `offset` to page incomplete
review items, plus optional `reviewer` and `pr_url` handoff metadata for the
packet header. `memory.acceptance_packet_archive_status` accepts `limit` and
`offset` to page generated packet snapshots.
`memory.acceptance_plan` and `memory.acceptance_template` also accept optional
`reviewer` and `pr_url` metadata to pre-fill generated record commands without
recording evidence or writing reports.
`memory.acceptance_packet_archive_retention_plan` previews generated manual
acceptance packet archive cleanup candidates after keeping the newest `keep`
snapshots. It is read-only and does not delete files or record evidence.

`memory.release_evidence` returns the same read-only local release evidence used
by `ai-dememory release-evidence --json` when the MCP root is the distribution
checkout, including top-level next actions plus compact setup and maintenance
summaries. Plain vault roots return `available=false` with an explanation
instead of failing. It accepts optional `reviewer` and `pr_url` metadata to
pre-fill the embedded manual acceptance plan and release handoff command arrays
without recording evidence.
`memory.release_evidence_report` renders the same Markdown report as
`ai-dememory release-evidence` without writing `reports/v2-release-evidence.md`
or recording evidence; the rendered report includes next actions and the
maintenance summary. It accepts the same optional `reviewer` and `pr_url`
metadata as the structured release-evidence tool.
`memory.publish_plan` returns the same manual TestPyPI or PyPI workflow
dispatch plan as `ai-dememory publish-plan --json` without writing files,
running publish or preflight commands, recording evidence, or uploading
packages. It may run local read-only inspection commands to collect release
evidence and resolve the workflow URL. It includes the trusted publishing
workflow path, confirmation inputs, release blockers, preflight command arrays,
and next actions.

`memory.consolidate` returns a dry-run consolidation report and includes
conflict scan evidence when `[conflicts].scan_on_consolidate = true`.
`memory.sleep_plan` returns safe consolidation candidates.
`memory.sleep_apply_reviewed` writes selected candidates only to
`inbox/sleep-consolidation/`.

`memory.review_false_positives` and `memory.review_conflicts` return structured
review candidates. `memory.false_positive_ignore`,
`memory.false_positive_unignore`, `memory.conflict_dismiss`,
`memory.conflict_keep`, and `memory.conflict_merge_proposal` only update
`.ai-dememory-ignore.toml` or write to `inbox/conflict-resolution/`.
`memory.review_false_positives` accepts `due_only=true` to return only due
false-positive suppressions with `returned_count` metadata.
`memory.review_stale_false_positives` returns ignored false-positive
suppressions whose current scanner finding no longer exists.
Review listing tools include `enabled` and compact `policy` metadata so clients
can distinguish disabled workflows from enabled workflows with no candidates.
False-positive ignore responses include a structured audit receipt with the
finding id, reviewer, reviewed date, review-after date, `review_due`,
`review_after_status`, and `canonical_memory_updated=false`. The review listing
returns the same derived due-status fields for suppressions.

`memory.review_modes` and `memory.review_plan` inspect LLM-assisted review
policy and include normalized false-positive/conflict policy settings from
`.ai-dememory.toml`. `memory.review_configure_mode` persists the active review
mode in `.ai-dememory.toml` and returns a receipt with
`canonical_memory_updated=false`. Canonical modes are `strict`, `balanced`,
`assisted`, and `autonomous_proposals`; legacy `batch` config resolves to
`autonomous_proposals`.
`memory.review_recommendation` stores advisory LLM/client review
recommendations under `inbox/review-recommendations/` and returns
`applies_review_decision=false` and `writes_canonical_memory=false`.
`memory.review_recommendations` lists pending advisory recommendation artifacts
and malformed files without applying review decisions, writing canonical memory,
or writing files.
`memory.review_recommendation_archive_status` lists archived accepted/rejected
recommendation artifacts without moving files, applying review decisions, or
editing canonical memory. `limit` and `offset` page large archive histories;
`invalid_offset` pages malformed archive artifacts; `recursive=true` includes
partitioned archive subdirectories.
`memory.review_recommendation_archive_restore_preview` previews reopening one
archived recommendation artifact without moving files, applying review
decisions, or editing canonical memory. `recursive=true` searches partitioned
archive subdirectories.
`memory.review_recommendation_outcome_report` renders the reviewed outcome
sign-off report without writing report files, applying recommendations, or
editing canonical memory. `limit` and `offset` page reviewed records, and
`invalid_offset` pages malformed active artifacts.
`memory.review_recommendation_outcome` records
accepted/rejected outcome status on recommendation artifacts without applying
recommendations or editing canonical memory.
False-positive and conflict outcome tools accept optional recommendation ids and
validate them against advisory recommendation artifacts before writing review
state. Linked receipts include recommendation id, path, action, and
policy-violation metadata.
If false-positive or conflict review is disabled in `.ai-dememory.toml`, the
corresponding MCP listing tools return empty candidate lists and write tools
reject the call before writing review state.

`private` and `sensitive` memories are excluded from default `memory.search` and
`memory.get` output unless `include_sensitive` is explicitly set. Resources and
generated prompts never expose private/sensitive memory by default.

Safety limits:

- `memory.search` caps result count at 50.
- `memory.write_proposal` caps proposal content at 20,000 characters.
- `memory.secret_scan` only accepts repository-relative paths when called
  through MCP.
- Tool results include structured content for clients and text content for
  compatibility.
