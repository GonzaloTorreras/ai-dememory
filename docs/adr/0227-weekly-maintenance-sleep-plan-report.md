# ADR 0227: Weekly Maintenance Sleep Plan Report

Status: Accepted

## Context

The v2 local maintenance loop already imports configured provider chats, rebuilds
generated indexes, recalculates weights, refreshes lifecycle artifacts, writes
weekly consolidation evidence, writes hook capture review reports, and runs
recall fixtures. Sleep consolidation is the newer compaction workflow, but
scheduled weekly maintenance still required a separate manual `ai-dememory
sleep plan` command to produce the generated review handoff.

That made recurring maintenance less complete for users who enabled weekly cron,
Task Scheduler, systemd, launchd, or Docker-backed local jobs after reviewing the
schedule plan.

## Decision

Weekly maintenance now writes the default generated sleep plan report at
`reports/sleep-plan.md` by calling the existing sleep report writer.

The maintenance result and generated maintenance report include
`sleep_plan_report`. `maintenance run --profile weekly --dry-run --json`
previews the target in `would_generate` and reports
`would_write_sleep_plan_report=true`.

`maintenance status` tracks `sleep_plan_report` in the generated artifact map
and `artifact_freshness`.

## Benefits

- Weekly scheduled maintenance produces compaction review evidence without a
  second manual command.
- The report uses the existing path-bounded, secret-scanned sleep report writer.
- Maintenance status, setup health, release evidence, package smoke, Docker
  smoke, and MCP smoke can see whether the generated sleep report is missing or
  stale.
- The behavior stays local and review-first.

## Limitations

- Weekly maintenance writes only the Markdown sleep plan report.
- It does not write sleep review packets under `inbox/sleep-consolidation/`.
- It does not apply canonical memory edits, archive memories, resolve conflicts,
  or promote durable memory.
- The report is overwritten at the default path on each weekly run.

## Future Risks

- Large vaults may make weekly sleep planning slower because it scans canonical
  memory and inbox Markdown before writing the report.
- If users need retained weekly sleep report history, this should add an
  explicit archive option rather than silently keeping timestamped copies.
- If sleep planning thresholds become configurable, maintenance status and
  release evidence must report the active thresholds so scheduled output remains
  auditable.

## Dependencies

- ADR 0004 defines safe sleep consolidation boundaries.
- ADR 0122 defines sleep report path validation and secret scanning.
- ADR 0154 defines maintenance profile dry-runs.
- ADR 0171 defines weekly maintenance hook capture report generation.
- ADR 0224 defines generated artifact freshness reporting.
- `scripts/maintenance.py` owns weekly maintenance orchestration.
- `scripts/sleep_consolidation.py` owns sleep report rendering and validation.
