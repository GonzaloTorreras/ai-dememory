# ADR 0048: MCP Manual Acceptance Plan

Status: Accepted for the v2 draft.

## Context

ADR 0047 added `ai-dememory acceptance plan` so release reviewers can see
remaining and blocked manual acceptance work with concrete example commands.
MCP clients and Codex plugin skills still had to shell out or infer next steps
from `memory.acceptance_status` and `memory.acceptance_verify`.

That left MCP-only release workflows able to inspect readiness but not the
reviewed next-action plan needed to finish manual acceptance.

## Decision

Expose `memory.acceptance_plan` as a read-only MCP tool.

The tool returns the same planner data as the CLI:

- completion, remaining, and blocked counts
- per-item status and latest reviewed record
- example passing and blocked `ai-dememory acceptance record` commands
- top-level next actions for release handoff

The MCP tool never records evidence, edits `inbox/release-acceptance/`, or
marks release readiness complete.

## Benefits

- Lets Codex plugin skills and MCP clients guide manual release acceptance
  without invoking a shell.
- Keeps manual evidence recording on the CLI while exposing read-only planning
  over MCP.
- Makes runtime smoke cover the same final handoff workflow that reviewers use
  before TestPyPI.

## Limitations

- The tool reports command examples only; it cannot prove that a human actually
  ran the manual checks.
- Blocked items remain release blockers until a later passing acceptance record
  exists.
- MCP clients may present the generated commands differently, so docs must keep
  the CLI as the canonical evidence writer.

## Future Risks

- If manual acceptance evidence moves outside Markdown records, the MCP planner
  must become a projection over the new evidence backend.
- If clients gain richer approval workflows, this tool may need to include
  machine-readable form fields instead of command strings.
- If release acceptance grows beyond local v2, reviewer identity and artifact
  provenance may need stronger guarantees than Markdown frontmatter.

## Dependencies

- ADR 0016 defines manual acceptance evidence records.
- ADR 0029 defines the final manual acceptance verification gate.
- ADR 0047 defines the shared CLI planner used by this MCP tool.
- `scripts/manual_acceptance.py` remains the canonical implementation for
  manual acceptance item status and planning.
