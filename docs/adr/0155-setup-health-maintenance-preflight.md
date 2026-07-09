# ADR 0155: Setup Health Maintenance Preflight

Status: Accepted

## Context

ADR 0153 added `ai-dememory setup health --json` and MCP
`memory.setup_health` as one passive setup status response. ADR 0154 added a
full maintenance profile dry-run, but that dry-run may read configured provider
files to compute exact `would_write` import candidates.

Setup health must remain safe as a first-run and plugin setup surface. It
should point users toward maintenance dry-runs without reading provider chats or
writing generated artifacts.

## Decision

Add a `maintenance_preflight` object to setup health.

The preflight includes:

- daily and weekly maintenance dry-run commands
- daily and weekly generated artifact targets
- configured, enabled, and import-ready provider counts from the no-read
  provider readiness summary
- explicit safety flags: `mutates_system=false`, `runs_commands=false`,
  `writes_files=false`, `reads_provider_files=false`, and
  `writes_import_candidates=false`

Setup health does not call the full maintenance dry-run. It only reports the
commands and artifact targets a user or plugin can review next.

## Benefits

- First-run setup can show maintenance readiness without forcing users to
  inspect separate scheduler, provider, and maintenance docs.
- Plugin skills can present the dry-run command before scheduler installation
  while keeping setup health safe for automatic reads.
- Runtime smoke covers that setup health includes maintenance preflight without
  reading provider files or writing files.

## Limitations

- The preflight does not compute exact provider `would_write` candidates.
  Users must run `ai-dememory maintenance run --profile daily --dry-run
  --json` when they want provider-file-level preview.
- Artifact targets are planned paths, not proof that a later write will succeed.
- The preflight does not prove host scheduler state or Docker availability.

## Future Work

- Add profile-specific setup health rendering if daily and weekly setup flows
  need different first-run guidance.
- Include a bounded count from the full maintenance dry-run only behind an
  explicit opt-in flag that permits provider file reads.
- Surface maintenance preflight in manual acceptance evidence templates if
  reviewers need a standard setup screenshot or report.

## Dependencies

- ADR 0153 defines setup health.
- ADR 0154 defines maintenance profile dry-run.
- ADR 0136 defines provider readiness without reading provider files.
- ADR 0133 defines the scheduler and plugin review-first boundary.
