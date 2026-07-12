---
name: memory-maintenance
description: Run or inspect ai-dememory daily/weekly maintenance, recall benchmarks, compaction reports, weights, cleanup, and scheduler status.
---

# Memory Maintenance

Maintenance remains CLI-first and requires the explicit MCP `admin` surface if
performed through MCP. The default `core` profile intentionally omits broad
maintenance, import, release, and acceptance schemas.

Use the CLI or MCP maintenance tools:

- Status: `ai-dememory maintenance status`
- Daily dry run: `ai-dememory maintenance run --profile daily --dry-run --json`
- Daily run: `ai-dememory maintenance run --profile daily`
- Weekly run: `ai-dememory maintenance run --profile weekly`
- Sleep plan: `ai-dememory sleep plan`
- Scheduler plan: `ai-dememory schedule plan --json`
- Scheduler dry run: `ai-dememory schedule setup --dry-run`
- Scheduler environment: `ai-dememory schedule doctor --json`
- Docker scheduler plan: `ai-dememory schedule plan --json --mode docker --image ai-dememory:local`
- Docker scheduler dry run: `ai-dememory schedule setup --dry-run --mode docker --image ai-dememory:local`
- Cron export: `ai-dememory schedule cron`
- Scheduler removal: `ai-dememory schedule remove`
- Provider import preview: `ai-dememory import-chats <provider> --dry-run --json`
- Recall fixture freshness: `ai-dememory recall-fixtures status`
- Recall review plan: `ai-dememory recall-fixtures review-plan`
- Reject/dismiss recall miss: `ai-dememory recall-fixtures review-miss --miss <path> --status rejected --reviewed-by <name> --reason <reason>`
- Vector readiness: `ai-dememory vector status`
- Durable provenance: `ai-dememory provenance`
- Manual acceptance status: `ai-dememory acceptance status`
- Manual acceptance plan: `ai-dememory acceptance plan`
- Manual acceptance template: `ai-dememory acceptance template --item <id>`
- Manual acceptance verification: `ai-dememory acceptance verify`
- Release evidence: `ai-dememory release-evidence --json`
- Review recommendation outcome report: `ai-dememory review recommendation-outcomes --json`
- Review recommendation outcome page: `ai-dememory review recommendation-outcomes --limit 50 --offset 50 --invalid-offset 50 --json`
- Review recommendation archive preview: `ai-dememory review recommendations-archive --json`
- Review recommendation archive status: `ai-dememory review recommendations-archive-status --json`
- Review recommendation malformed archive page: `ai-dememory review recommendations-archive-status --limit 50 --invalid-offset 50 --json`
- Review recommendation archive restore preview: `ai-dememory review recommendations-archive-restore --id <rec_id> --json`

Daily maintenance imports enabled providers into inbox, runs secret scan,
rebuilds the index, refreshes the graph cache, recalculates weights, and writes
lifecycle score artifacts. Run `maintenance run --profile daily --dry-run
--json` before manual or scheduled runs to preview provider imports and
generated artifacts without writing files. Preview a single provider with
`import-chats --dry-run` before enabling scheduled imports. Repeat provider
imports skip candidates with the same stable fingerprint instead of creating
duplicate inbox files.

Maintenance status reports generated artifact state for the index, graph,
weights, lifecycle score JSON, lifecycle report, generated packet archive
cleanup counts, false-positive review due counts, conflict review counts, hook
capture review counts, and advisory review recommendation counts. It does not
delete generated packet archives.

Weekly maintenance also writes a consolidation report, writes
`reports/sleep-plan.md`, runs recall fixtures when present, and removes old
maintenance reports.

Sleep consolidation writes review packets under `inbox/sleep-consolidation/`
only when explicitly proposed or applied by id/all. Weekly maintenance writes
the generated Markdown sleep plan report only. It must not mutate canonical
memory.

Maintenance does not promote durable memories.

Docker schedules still use the host scheduler and bind-mount the selected vault
at `/memory`; they are not remote services.

Cron export only prints crontab lines for review. It does not install them.
MCP `memory.schedule_plan` returns equivalent `cron_entries` with
`mutates_system=false` for review inside Codex.

Reviewed recommendation archives are CLI-only. Use
`ai-dememory review recommendation-outcomes --json` first when an offline
sign-off packet is needed; it writes only a generated report under `reports/`
and does not apply recommendations. Add `--offset` for reviewed recommendation
records or `--invalid-offset` for malformed active artifacts when the outcome
packet is large. Then use `ai-dememory review
recommendations-archive --json` first, then add `--apply` only after confirming
accepted/rejected artifacts should move to `archive/review-recommendations/`.
Use
`ai-dememory review recommendations-archive-status --json` to inspect archived
recommendation outcomes without moving files; add `--offset` for valid records
or `--invalid-offset` for malformed archive artifacts. To reopen one archived
advisory artifact, preview `ai-dememory review recommendations-archive-restore
--id <rec_id> --json`, then add `--apply` only after confirming the active inbox
path does not already exist. Add `--recursive` to archive status or restore
previews when archived recommendation artifacts are grouped under date or
project partitions.

For MCP-based quality and release readiness checks, use read-only
`memory.recall_fixture_status`, `memory.recall_miss_candidate`, `memory.recall_review_plan`, `memory.recall_review_packet`, `memory.recall_review_packet_archive_status`, `memory.recall_miss_review`, `memory.vector_status`,
`memory.provenance_status`, `memory.acceptance_status`,
`memory.acceptance_verify`, `memory.acceptance_plan`,
`memory.acceptance_template`, `memory.acceptance_packet`,
`memory.acceptance_packet_archive_status`, and
`memory.release_evidence`, `memory.release_evidence_report`, and
`memory.review_recommendation_outcome_report`.
Use optional `reviewer` and `pr_url` with `memory.recall_review_packet` when a
weekly recall review packet should carry handoff context for a review or PR.
Use `memory.recall_review_packet_archive_status` and
`memory.recall_review_packet_archive_retention_plan` to list generated recall
packet snapshots and preview cleanup candidates without writing files,
fixtures, deleting archives, or miss outcomes.
Use `limit` and `offset` with `memory.acceptance_packet` when incomplete manual
acceptance items exceed one practical review page. Pass optional `reviewer` and
`pr_url` when the generated packet should include handoff context for a review
or PR. Use `memory.acceptance_packet_archive_status` and
`memory.acceptance_packet_archive_retention_plan` to list generated manual
acceptance packet snapshots and preview cleanup candidates without writing
files, deleting archives, or recording evidence.
`memory.release_evidence` and `memory.release_evidence_report` are available in
the distribution checkout and return unavailable in plain vaults. Record
reviewed manual acceptance evidence and promote reviewed recall misses only
through the CLI. Rejected or dismissed recall misses can be closed through
`memory.recall_miss_review` without writing fixtures or canonical memory.
