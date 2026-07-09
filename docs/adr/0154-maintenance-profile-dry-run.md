# ADR 0154: Maintenance Profile Dry Run

Status: Accepted

## Context

Daily and weekly maintenance can import enabled provider chats, rebuild
generated indexes, refresh graph and lifecycle artifacts, recalculate weights,
write reports, and, for weekly runs, write consolidation, hook capture, and
recall review artifacts. Scheduler setup is already review-first, and provider
imports have a single-provider dry-run, but users did not have one command that
previewed the whole maintenance profile before running it manually or installing
a recurring schedule.

## Decision

Add `ai-dememory maintenance run --profile <daily|weekly> --dry-run --json`
and MCP `memory.maintenance_run` argument `dry_run=true`.

The dry-run:

- previews enabled provider imports with the existing provider import dry-run
  path
- reports generated artifact targets for index, graph, weights, lifecycle, and
  maintenance reports
- reports weekly-only recall/consolidation/hook-capture-report/cleanup work
- returns explicit safety flags: `mutates_system=false`, `writes_files=false`,
  and `writes_import_candidates=false`
- does not take the maintenance lock, rebuild indexes, write reports, create
  inbox files, install scheduler state, or promote memory

## Benefits

- Users can inspect the full daily/weekly maintenance plan before enabling a
  host scheduler.
- Codex plugin skills can present one profile preview instead of stitching
  together provider dry-runs and artifact expectations manually.
- Install smoke and MCP runtime smoke cover the preview path without creating
  generated artifacts.

## Limitations

- The dry-run may read configured provider files to compute `would_write`
  import candidates. It does not read provider files when no provider is
  enabled.
- It previews generated artifact paths and planned work; it does not prove that
  a later write will succeed.
- It does not run the repository-wide secret scan that real maintenance runs
  before indexing.

## Future Work

- Add optional per-provider limits to the maintenance dry-run if users need a
  smaller preview for very large chat folders.
- Include dry-run summaries in setup health if maintenance preflight status
  becomes part of first-run readiness.
- Add a report writer for dry-run previews only if reviewers need durable
  evidence artifacts.

## Dependencies

- ADR 0137 defines provider import dry-run behavior.
- ADR 0138 defines idempotent provider import fingerprints.
- ADR 0133 defines the scheduler and plugin review-first boundary.
- ADR 0153 defines combined setup health summaries.
