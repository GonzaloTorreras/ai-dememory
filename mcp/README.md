# MCP Server

The local stdio server lives in `mcp/server/memory_mcp.py`. It exposes memory
as MCP tools, resources, and prompts while keeping Markdown canonical.

See `docs/mcp-v2.md` for the production-readiness target and hardening plan.
See `docs/mcp-v2-gap-analysis.md` for implemented, deferred, and out-of-scope
protocol features.

The current inventory is 74 MCP tools:

- `memory.acceptance_status`: returns reviewed manual release acceptance
  evidence status.
- `memory.acceptance_verify`: returns manual acceptance completion state
  without recording evidence.
- `memory.acceptance_plan`: returns remaining and blocked manual acceptance
  next actions without recording evidence. Optional `reviewer` and `pr_url`
  arguments pre-fill generated record commands.
- `memory.acceptance_template`: returns a single manual acceptance evidence
  template without recording evidence. Optional `reviewer` and `pr_url`
  arguments pre-fill the generated record command.
- `memory.acceptance_packet`: renders the manual acceptance review packet
  without writing reports or recording evidence. Use `limit` and `offset` to
  page incomplete review items. Optional `reviewer` and `pr_url` arguments
  pre-fill handoff metadata in the rendered packet.
- `memory.acceptance_packet_archive_status`: lists generated manual acceptance
  packet archives without writing files or recording evidence.
- `memory.acceptance_packet_archive_retention_plan`: plans generated manual
  acceptance packet archive pruning without deleting files or recording
  evidence.
- `memory.release_evidence`: returns read-only local v2 release evidence in a
  distribution checkout, including next actions plus compact setup and
  maintenance summaries. Optional `reviewer` and `pr_url` metadata pre-fill
  manual acceptance and handoff commands without recording evidence.
- `memory.release_evidence_report`: renders the v2 release evidence Markdown
  report, including next actions plus setup and maintenance summaries, without
  writing report files or recording evidence. It accepts the same optional
  `reviewer` and `pr_url` metadata.
- `memory.publish_plan`: returns manual TestPyPI or PyPI publish workflow
  dispatch inputs, preflight commands, blockers, and false side-effect flags
  without uploading packages, writing files, or running publish/preflight
  commands. It may run local read-only inspection commands for release evidence
  and workflow URL resolution.
- `memory.roadmap_status`: returns read-only v2 operational roadmap phase
  status, including implemented, gated, and missing-evidence counts.
- `memory.capture_import`: captures explicit text or a repository-local file into
  `inbox/imports/` for review.
- `memory.capture_miss`: writes reviewed recall-miss candidates under
  `inbox/recall-feedback/`.
- `memory.recall_miss_candidate`: checks whether an expected memory is outside
  the accepted rank window without writing recall feedback.
- `memory.consolidate`: generates a dry-run consolidation report, including
  conflict scan evidence when `[conflicts].scan_on_consolidate = true`.
- `memory.conflict_dismiss`: records a reviewed conflict dismissal and returns
  an audit receipt without editing canonical memory; optional
  `recommendation_id` links to an advisory recommendation artifact.
- `memory.conflict_keep`: records a reviewed keep decision and returns an audit
  receipt with reviewer metadata without editing canonical memory; optional
  `recommendation_id` links to an advisory recommendation artifact.
- `memory.conflict_merge_proposal`: writes conflict merge proposals under
  `inbox/conflict-resolution/` and returns an audit receipt; optional
  `recommendation_id` links to an advisory recommendation artifact.
- `memory.context`: assembles token-budgeted context from safe search results
  using an explicit query or `auto: true` working-memory query, with optional
  vault-configured defaults and explanation rendering.
- `memory.doctor`: returns local readiness checks, selected profile, and status
  summary.
- `memory.validate_status`: returns structured validation and conflict scan
  status without mutating files.
- `memory.false_positive_ignore`: records reviewed secret-scan suppressions and
  returns an audit receipt with review-after due status without editing
  canonical memory; optional `recommendation_id` links to an advisory
  recommendation artifact.
- `memory.false_positive_unignore`: records reviewed removal of a
  false-positive suppression without editing canonical memory; optional
  `recommendation_id` links to an advisory recommendation artifact.
- `memory.get`: returns a memory document by id or path.
- `memory.git_lessons`: inspects local git history and previews review-first
  lesson candidates by default; set `dry_run=false` to write candidates to
  `inbox/git-lessons/`, with repeated candidates skipped as `already captured`.
- `memory.graph`: returns generated memory graph nodes and edges.
- `memory.hook_config`: returns Codex or Claude hook configuration fragments.
- `memory.hook_events`: returns supported provider hook metadata.
- `memory.hook_status`: returns managed hook instruction status and bounded
  hook capture counts, including review outcome counts and review-after due
  state, without writing files or reading raw payload bodies. Capture summaries
  can be filtered by provider, event, review status, created date window, and
  review-after date window.
- `memory.hook_capture_review`: records a reviewed outcome on a selected
  `inbox/session-events/` capture without promoting canonical memory.
- `memory.import_chats`: imports configured provider chats into review inboxes;
  accepts `dry_run=true` to return `would_write` without writing candidates, and
  skips repeated provider candidates with reason `already imported`.
- `memory.lifecycle_scores`: returns generated lifecycle scoring data.
- `memory.maintenance_run`: runs an opt-in daily or weekly maintenance profile;
  pass `dry_run=true` to preview provider imports and generated artifacts
  without writing files. Dry-runs report that generated packet archives are
  reviewed but not deleted. Weekly previews include the hook capture report
  target.
- `memory.maintenance_status`: returns provider config, provider import
  readiness, false-positive review due counts, stale suppression counts,
  conflict review counts, advisory review recommendation counts, hook capture
  review counts, generated packet archive cleanup counts, schedule, generated
  artifact state/freshness, report, and lock status without deleting archives
  or refreshing artifacts.
- `memory.mark_seen`: records retrieval usage in the SQLite `retrieval_log` and
  returns a structured feedback receipt.
- `memory.outcome`: records good/bad memory usefulness feedback and returns a
  structured lifecycle receipt with counters and update metadata.
- `memory.provenance_status`: audits durable memories for reviewed provenance
  metadata.
- `memory.providers_detect`: detects known local LLM provider folders.
- `memory.providers_plan`: returns reviewable provider configure dry-run,
  configure, import dry-run, and import command arrays without mutating config
  or reading provider files.
- `memory.providers_status`: returns provider import readiness without reading
  or importing chat files.
- `memory.reindex`: runs secret scan, validation, and index rebuild.
- `memory.recall_fixture_status`: reports recall fixture provenance and
  reviewed-promotion freshness.
- `memory.recall_miss_review`: records a reviewed reject or dismiss outcome for
  a recall miss without writing fixture files or canonical memory.
- `memory.recall_review_plan`: reports pending, invalid, and bounded recent
  resolved recall miss review work plus candidate-check guidance without
  writing fixture files.
- `memory.recall_review_packet`: renders the weekly recall review packet
  without writing reports, fixtures, or miss outcomes. Use `limit`,
  `pending_offset`, and `invalid_offset` to page pending and malformed miss
  sections. Optional `reviewer` and `pr_url` arguments pre-fill handoff
  metadata in the rendered packet.
- `memory.recall_review_packet_archive_status`: lists generated recall review
  packet archives without writing files, fixtures, or miss outcomes.
- `memory.recall_review_packet_archive_retention_plan`: plans generated recall
  review packet archive pruning without deleting files, fixtures, or miss
  outcomes.
- `memory.review_conflicts`: returns duplicate, preference, project decision,
  and restricted-memory conflict candidates, plus enabled/policy metadata.
- `memory.review_false_positives`: returns deterministic false-positive review
  candidates with derived `review_due` and `review_after_status` fields; pass
  `due_only=true` to return only due suppressions. The response includes
  enabled/policy metadata.
- `memory.review_stale_false_positives`: returns ignored false-positive
  suppressions whose current scanner finding no longer exists, plus
  enabled/policy metadata.
- `memory.review_modes`: returns active review mode configuration plus
  normalized review policy defaults from `.ai-dememory.toml`.
- `memory.review_configure_mode`: persists the active review mode without
  editing canonical memory.
- `memory.review_plan`: returns policy guidance for the current review mode and
  configured false-positive/conflict policy.
  Canonical modes are `strict`, `balanced`, `assisted`, and
  `autonomous_proposals`; legacy `batch` resolves to `autonomous_proposals`.
  If false-positive or conflict review is disabled in `.ai-dememory.toml`, the
  corresponding list tools return no candidates and write tools reject the call.
- `memory.review_recommendation`: stores advisory LLM/client review
  recommendations under `inbox/review-recommendations/` with
  `applies_review_decision=false` and `writes_canonical_memory=false`.
- `memory.review_recommendations`: lists pending advisory review
  recommendations and malformed recommendation artifacts without applying
  review decisions or writing files.
- `memory.review_recommendation_archive_status`: lists archived accepted or
  rejected advisory recommendation artifacts without moving files or applying
  decisions. Use `limit` and `offset` to page large histories, and
  `invalid_offset` to page malformed archive artifacts. Set `recursive=true` to
  include date or project partitions under the selected archive root.
- `memory.review_recommendation_archive_restore_preview`: previews reopening one
  archived recommendation artifact without moving files, applying review
  decisions, or mutating canonical memory. Set `recursive=true` to search
  partitioned archive directories.
- `memory.review_recommendation_outcome_report`: renders the reviewed
  recommendation outcome sign-off report without writing files, applying review
  decisions, or mutating canonical memory. Use `limit` and `offset` to page
  reviewed records, and `invalid_offset` to page malformed active artifacts.
- `memory.review_recommendation_outcome`: records accepted/rejected status on
  advisory recommendation artifacts without applying the recommendation or
  writing canonical memory.
- `memory.schedule_plan`: returns installed-CLI or Docker platform scheduler
  commands, daily/weekly run commands, and reviewed cron export entries without
  installing them.
- `memory.schedule_status`: returns configured scheduler settings, review due
  summary, and platform status commands without querying or mutating the OS
  scheduler; invalid persisted scheduler config returns validation errors and
  no status commands.
- `memory.schedule_environment`: checks local scheduler, Docker, and crontab
  command availability without running those commands.
- `memory.search`: reads the SQLite index and returns ranked results with path,
  source, confidence, status, snippets, numeric `why` components, and matched
  evidence fields such as `matched_terms` and `matched_fields`.
- `memory.secret_scan`: scans selected paths or all repo text artifacts.
- `memory.setup_plan`: returns review-first vault, MCP, provider, hook, and
  scheduler setup command arrays without mutating files.
- `memory.setup_health`: returns combined validation status, context config
  status, manual acceptance readiness, recall review status, vector readiness,
  scheduler environment/status, provider readiness, maintenance preflight
  commands, generated artifact, generated packet archive cleanup, lock, and
  review queue health without running commands, writing files, or deleting
  archives.
- `memory.sleep_apply_reviewed`: writes selected sleep consolidation review
  packets under `inbox/sleep-consolidation/`.
- `memory.sleep_plan`: returns safe sleep consolidation candidates.
- `memory.vector_status`: reports whether recall fixtures justify a future
  vector search experiment.
- `memory.working_current`: reads generated `working/current.json` state.
- `memory.working_status`: summarizes current working state, recent-session
  presence, and recent handoffs.
- `memory.working_handoff`: writes generated session handoffs under
  `working/handoffs/`.
- `memory.working_snapshot`: writes generated current working state under
  `working/`.
- `memory.write_proposal`: writes scanned proposals to `inbox/llm-captures/`.

Private and sensitive memories are excluded unless a tool explicitly accepts and
receives an `include_sensitive` request.

Resources:

- `memory://id/{id}`: public/internal memory by stable id.
- `memory://path/{path}`: public/internal memory by repository-relative path.

Prompts:

- `memory_recall_context`: recall relevant memory for a task.
- `memory_capture_proposal`: create a safe write-proposal workflow.
- `memory_review_inbox`: guide human review of proposed captures.

Utilities:

- `initialize`: negotiates `2025-11-25` or `2024-11-05`.
- `notifications/initialized`: accepted as lifecycle notification.
- `ping`: returns an empty result for connection-health checks.

Validate locally:

```bash
python3 mcp/server/memory_mcp.py --list-tools
python3 scripts/mcp_inventory.py --check-docs
python3 mcp/server/memory_mcp.py --call memory.search --args '{"query":"codex","limit":3}'
```
