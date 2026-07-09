# ADR 0222: Release Evidence Maintenance Summary

Status: Accepted

## Context

Release evidence already includes automated checks, manual acceptance state,
recall quality state, vector readiness, and a compact setup health summary.
ADR 0221 added generated packet archive cleanup counts to maintenance status and
generated maintenance reports, but final release handoffs still did not show
that maintenance state directly.

Reviewers preparing a v2 release need one handoff artifact that explains both
release blockers and local maintenance pressure without running maintenance,
reading provider files, applying review recommendations, or pruning generated
archives.

## Decision

Add a compact `maintenance_summary` object to release evidence and render it in
the Markdown report.

The summary includes:

- recent maintenance report count and latest report path;
- maintenance lock state;
- generated artifact present/missing counts;
- provider import readiness counts without reading provider files;
- false-positive, stale suppression, conflict, and advisory recommendation
  review counts; and
- generated packet archive total/prunable counts with `deletes_files=false`.

The summary is read-only and does not become a release blocker by itself.
Existing release blockers continue to come from dirty worktrees, automated
warnings/failures, recall quality gates, vector readiness review, and manual
acceptance state.

## Benefits

- Release reviewers get maintenance context in the same report as acceptance,
  recall, vector, setup, and publish evidence.
- Generated packet archive cleanup pressure is visible at release handoff time
  without requiring a separate maintenance status command.
- The handoff remains safe for local/private vaults because it does not read
  provider chat files or delete archives.

## Limitations

- The summary is compact and omits the full maintenance status payload.
- It reflects the current local checkout and vault at report generation time.
- It does not verify that host scheduler jobs are installed or running.

## Future Risks

- If maintenance status gains configurable retention policies, release evidence
  should report the active policy source.
- If generated artifact status becomes large or multi-vault, the summary may
  need pagination or per-profile grouping.
- If maintenance findings become release-blocking later, that must be modeled
  as explicit blockers rather than inferred from this informational summary.

## Dependencies

- ADR 0154 defines maintenance profile dry-runs.
- ADR 0185 defines setup health summaries in release evidence.
- ADR 0221 defines generated packet archive summaries in maintenance status.
- `scripts/release_evidence.py` owns release evidence JSON and Markdown.
- `scripts/maintenance.py` owns maintenance status.
