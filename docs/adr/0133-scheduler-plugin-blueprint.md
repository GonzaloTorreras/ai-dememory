# ADR 0133: Scheduler And Plugin Blueprint

## Status

Accepted

## Context

The v2 local memory loop now includes maintenance profiles, scheduler planning,
Codex plugin skills, MCP setup tools, provider import planning, and hook
metadata capture. These pieces are implemented across several files, but users
need one stable contract explaining what is passive, what is opt-in, and what a
Codex plugin installation is allowed to do.

The important safety boundary is that package and plugin installation cannot
silently create recurring jobs, read chat provider folders, import private
conversations, or promote durable memory.

## Decision

Add `docs/scheduler-plugin-blueprint.md` as the release-required implementation
blueprint for scheduler and Codex plugin behavior.

The blueprint defines:

- host scheduler ownership for recurring jobs
- installed CLI and local Docker execution modes
- daily and weekly maintenance profile responsibilities
- the Codex plugin artifact shape
- the review-first MCP allowlist boundary
- hook event boundaries
- the recommended setup flow using `setup plan`, hook dry-runs, and scheduler
  dry-runs

The release checklist and release check required-doc list must include this
blueprint and ADR.

## Consequences

- Gives future scheduler work a single design anchor instead of scattering the
  contract across install docs, plugin docs, and MCP docs.
- Keeps plugin install passive while still documenting how users opt into
  recurring maintenance.
- Makes scheduler and plugin drift visible during release checks.

## Limitations

- This is documentation and guard coverage, not a new scheduler capability.
- Host scheduler health is still not queried by MCP tools; status tools return
  reviewable commands only.
- Real-client and real-scheduler acceptance still require human-recorded
  evidence.

## Future Work

- Add real host-scheduler acceptance evidence before final v2 release if users
  expect scheduler installation to be part of the release claim.
- Revisit plugin per-tool approval metadata if Codex plugin manifests add
  richer permission controls.
- Keep Docker mode local-only unless a separate remote deployment design is
  approved.

## Dependencies

- ADR 0026 defines Docker maintenance schedule planning.
- ADR 0028 defines cron export without automatic crontab writes.
- ADR 0066 defines read-only MCP scheduler status.
- ADR 0068 defines the guarded plugin MCP tool surface.
- ADR 0079 defines read-only local setup planning.

## References

- `docs/scheduler-plugin-blueprint.md`
- `docs/scheduler.md`
- `docs/codex-plugin.md`
- `docs/hooks.md`
- `scripts/schedule_memory.py`
- `scripts/setup_plan.py`
