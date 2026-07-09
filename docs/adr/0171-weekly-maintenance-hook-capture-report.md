# ADR 0171: Weekly Maintenance Hook Capture Report

## Status

Accepted

## Context

ADR 0170 added `ai-dememory hooks captures --write-report` so reviewers can
create a frontmatter-only hook capture handoff artifact. Weekly maintenance
already writes slower review artifacts such as consolidation dry-run reports and
recall fixture summaries, but it did not include hook capture review evidence.

Operators running scheduled weekly maintenance need one local command that
refreshes review evidence without promoting memory or reading raw hook payload
bodies.

## Decision

Weekly maintenance now writes `reports/hook-captures.md` using the same
frontmatter-only report writer as `ai-dememory hooks captures --write-report`.

The weekly maintenance result and generated maintenance report include:

- `hook_capture_report`
- `hook_captures`
- `hook_capture_review_due`

`maintenance run --profile weekly --dry-run --json` includes
`reports/hook-captures.md` in `would_generate` and reports
`would_write_hook_capture_report=true`. Daily maintenance keeps this flag false.

`maintenance status` includes hook capture summary counts and generated artifact
state for `reports/hook-captures.md`.

## Benefits

- Weekly review gets hook capture evidence with the same command that refreshes
  recall, consolidation, lifecycle, and maintenance reports.
- The scheduled path stays local-first and review-first.
- Operators can preview the hook report target before enabling a recurring job.
- Routine maintenance still avoids raw payload bodies.

## Limitations

- Daily maintenance does not write the hook capture report.
- The hook capture report is overwritten at `reports/hook-captures.md`; long-term
  archival remains a reviewer responsibility.
- The report summarizes bounded frontmatter metadata and does not decide whether
  any capture should become canonical memory.

## Future Work

- Add configurable maintenance report bundles if users need separate daily,
  weekly, or release-evidence profiles.
- Add reviewed hook capture outcomes if session-event review needs lifecycle
  state beyond Markdown candidates.

## Dependencies

- ADR 0170 defines the hook capture review report writer.
- ADR 0154 defines maintenance profile dry-run behavior.
- `scripts/maintenance.py` owns weekly maintenance orchestration.
- `scripts/hook_event.py` owns hook capture report rendering.
