# ADR 0185: Release Evidence Setup Health Summary

Status: Accepted

## Context

The v2 setup-health surface has grown into the read-only local status summary
for validation, context defaults, scheduler readiness, provider readiness,
maintenance preflight, hook capture review, recall review, vector readiness,
manual acceptance, false-positive review, and conflict review.

Release evidence is the final handoff artifact, but before this change it
required reviewers to run `ai-dememory setup health --json` separately to see
whether local setup had unresolved review actions. That split made release
handoffs less complete even though setup health itself is passive and already
safe for MCP clients.

## Decision

Add `setup_health_summary` to `ai-dememory release-evidence --json`, the
Markdown release-evidence report, and MCP `memory.release_evidence`.

The field is a compact summary derived from `setup_health(root)`. It includes:

- setup readiness, platform, and mode;
- validation and context-default status;
- scheduler environment/config readiness;
- manual acceptance counts;
- recall review status and counts;
- vector readiness decision and `creates_embeddings=false`;
- hook capture review-due count with `reads_raw_payloads=false`;
- provider readiness counts;
- false-positive and conflict review counts; and
- setup next actions.

The summary preserves read-only flags:

- `mutates_system=false`;
- `runs_commands=false`; and
- `writes_files=false`.

The summary does not add a new release blocker. Release blockers remain focused
on dirty worktree state, automated release-check failures/warnings, recall
freshness, vector-readiness review, and manual acceptance evidence. Setup health
can report local scheduler or provider setup gaps that are useful in a handoff
without making `release-evidence --strict` depend on a specific workstation.

## Benefits

- Final release evidence includes the same setup next actions exposed to MCP
  clients and setup guides.
- Reviewers no longer need a separate setup-health command to see local setup
  gaps during a release handoff.
- The JSON remains smaller than embedding the full setup-health payload.
- Setup-health privacy boundaries are carried into release evidence, including
  no raw hook payload reads and no provider file reads.

## Limitations

- The summary is intentionally compact and omits full nested setup-health
  details; users should run `ai-dememory setup health --json` for diagnostics.
- A setup-health readiness issue is not automatically a release blocker unless
  another release-evidence blocker already covers it.
- The summary reflects the current local platform and environment, so scheduler
  readiness can differ between reviewer machines.

## Future Work

- Add an optional expanded release-evidence mode if reviewers need the full
  setup-health payload embedded in generated reports.
- Revisit whether specific setup-health fields should become release blockers
  after more real release handoffs.
- Add stable machine-readable severity levels to setup next actions if clients
  need prioritization.

## Dependencies

- ADR 0153 defines setup health as a read-only setup surface.
- ADR 0179, ADR 0180, ADR 0181, ADR 0182, and ADR 0183 add setup-health fields.
- ADR 0184 adds release-evidence vector readiness.
- `scripts/setup_plan.py` owns setup health assembly.
- `scripts/release_evidence.py` owns release evidence rendering.
