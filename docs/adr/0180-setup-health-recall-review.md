# ADR 0180: Setup Health Recall Review

Status: Accepted

## Context

Recall quality is a v2 release concern. `release-evidence` already includes
`recall_fixture_freshness`, `recall_fixture_review_plan`, and a
`recall_fixture_review` blocker while fixtures are seed-only, stale, pending,
or invalid. MCP clients can also call `memory.recall_fixture_status` and
`memory.recall_review_plan` directly.

Setup health is the first-run local status surface, but before this ADR it did
not show recall review state. Users could see scheduler, provider,
maintenance, hook, validation, false-positive, and conflict state while missing
the recall-quality action that still blocks v2 release readiness.

## Decision

Add `recall_review` to `ai-dememory setup health --json` and MCP
`memory.setup_health`. The field reuses `recall_fixture_review_plan` and
therefore includes fixture freshness, pending and invalid miss counts, bounded
resolved miss evidence, candidate-check guidance, and next actions.

Setup health remains read-only. It does not write recall reports, promote
fixtures, create miss files, rebuild indexes, read provider files, or mutate
canonical memory. Stale, pending, or invalid recall review state adds setup
health next actions, but it does not make top-level `ready` false because a
fresh vault can still be locally operable while recall fixture review remains a
release-quality task.

## Benefits

- First-run and MCP setup flows now show recall-quality work in the same passive
  health response as validation and maintenance state.
- The field reuses the same recall review planner as CLI, MCP recall tools, and
  release evidence, avoiding another recall-quality contract.
- Runtime smoke protects that setup health exposes recall review actions.
- Users can see why release evidence may still block on recall quality without
  running release evidence first.

## Limitations

- The field can include bounded recall miss metadata, though secret-like fields
  are redacted by the existing recall review planner.
- `ready` remains operational readiness, not release readiness.
- The field reports review guidance but does not perform weekly recall review.

## Future Risks

- If recall review metadata grows larger, setup health may need a compact mode
  or stricter bounded output.
- If release readiness and setup readiness are unified later, recall review may
  need a separate severity flag instead of only next actions.

## Dependencies

- ADR 0111 embeds recall review planning in release evidence.
- ADR 0179 adds validation status to setup health.
- `scripts/recall_fixtures.py` owns recall review planning and redaction.
- `scripts/setup_plan.py` owns setup-health assembly.
- `scripts/mcp_runtime_smoke.py` verifies the MCP setup-health path.
