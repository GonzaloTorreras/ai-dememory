# ADR 0182: Setup Health Manual Acceptance

Status: Accepted

## Context

The v2 release process separates automated readiness from manual acceptance.
Manual checks are recorded with `ai-dememory acceptance record`, planned with
`ai-dememory acceptance plan`, and exposed over MCP through
`memory.acceptance_status`, `memory.acceptance_verify`, `memory.acceptance_plan`,
and `memory.acceptance_template`.

`setup health` is the combined local status surface used by setup guides and
plugin skills. Before this change, it showed validation, context config, recall
review, scheduler, provider, hook, generated artifact, false-positive, and
conflict state, but not whether release-only manual acceptance remained.

## Decision

Add a compact `manual_acceptance` object to `ai-dememory setup health --json`
and MCP `memory.setup_health`.

The object reports:

- `complete`
- `total`
- `completed_count`
- `blocked_count`
- `remaining_count`
- `next_actions`
- `mutates_system=false`
- `runs_commands=false`
- `writes_files=false`
- `records_evidence=false`

The data is derived from the existing `acceptance_plan` implementation. Setup
health adds top-level next actions when blocked or remaining manual acceptance
items exist.

## Benefits

- Setup and plugin flows can show release-readiness gaps without calling a
  separate acceptance tool first.
- Reviewers see that manual acceptance is still required even when automated
  setup health is otherwise clean.
- The payload stays compact enough for routine setup diagnostics.
- Evidence recording remains explicit and human-reviewed.

## Limitations

- Setup health does not list every acceptance item or suggested artifact; callers
  should use `ai-dememory acceptance plan --json` or MCP
  `memory.acceptance_plan` for full detail.
- A clean automated setup health response does not mean release-ready unless
  `manual_acceptance.complete` is also true.
- This does not run a GUI MCP client, publish to TestPyPI, or record proof.

## Future Work

- Add client-specific rendering if setup-health output becomes too large for
  plugin surfaces.
- Include acceptance report freshness if reviewed records need expiry dates.
- Consider linking setup-health manual acceptance actions to generated
  acceptance plan reports when a stable report manifest exists.

## Dependencies

- ADR 0016 defines manual acceptance evidence records.
- ADR 0029 defines the manual acceptance verification gate.
- ADR 0047 defines manual acceptance planning.
- ADR 0048 exposes manual acceptance planning over MCP.
- ADR 0153 defines setup health as a read-only local setup surface.
- `scripts/manual_acceptance.py` owns acceptance planning.
- `scripts/setup_plan.py` owns setup health assembly.
