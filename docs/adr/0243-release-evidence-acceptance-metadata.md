# ADR 0243: Release Evidence Acceptance Metadata

Status: Accepted.

## Context

ADR 0242 added reviewer and PR URL metadata to manual acceptance plans and
templates. `release-evidence --pr-url` already accepted a PR URL for release
handoffs, but the embedded `manual_acceptance_plan` still used placeholder
artifact commands. The top-level handoff commands also pointed reviewers at the
acceptance packet, but not the lighter metadata-aware plan and template
commands.

## Decision

Add optional reviewer metadata to release evidence:

- `ai-dememory release-evidence --reviewer "Reviewer Name"`
- environment fallback `AI_DEMEMORY_REVIEWER`
- MCP `memory.release_evidence` argument `reviewer`
- MCP `memory.release_evidence_report` argument `reviewer`

`build_release_evidence` now passes reviewer and PR URL metadata into the
embedded manual acceptance plan. `handoff_commands` includes metadata-aware
`acceptance_plan` and `acceptance_template` command arrays, and existing
release-evidence, acceptance-packet, and recall-packet handoff commands carry
the same reviewer value.

## Benefits

- Final release evidence handoffs produce acceptance commands that are already
  tied to the reviewer and PR context.
- Reviewers can use a single release-evidence report as the source for packet,
  plan, template, strict-check, and publish-planning commands.
- CLI and MCP release evidence stay aligned with the acceptance planning
  surfaces.

## Limitations

- Reviewer metadata is reviewer-supplied and not authenticated.
- A PR URL in generated commands is an artifact hint, not proof that a manual
  check passed.
- Summary text remains intentionally item-specific and must still be edited by
  the reviewer before recording evidence.
- Existing generated release evidence reports are not backfilled.

## Future Risks

- If reviewer identity becomes signed or externally verified, release evidence
  should carry the stronger identity object instead of a plain string.
- If acceptance records support multiple structured artifacts, release evidence
  should pre-fill those artifact fields instead of only a PR URL.
- If release evidence grows many command groups, handoff command rendering may
  need grouping to stay readable.

## Dependencies

- ADR 0209 defines manual acceptance packet reviewer and PR URL metadata.
- ADR 0235 defines release evidence handoff commands.
- ADR 0242 defines manual acceptance plan/template metadata.
- `scripts/release_evidence.py` owns release evidence assembly and Markdown
  rendering.
- `mcp/server/memory_mcp.py` exposes release evidence through MCP.
