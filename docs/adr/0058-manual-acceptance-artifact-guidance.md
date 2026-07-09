# ADR 0058: Manual Acceptance Artifact Guidance

Status: Accepted for the v2 draft.

## Context

Manual acceptance is intentionally separate from automated release gates. ADR
0047 added `ai-dememory acceptance plan`, ADR 0048 exposed the same plan over
MCP, and ADR 0049 embedded it in release evidence. The plan listed remaining
checks and example record commands, but reviewers still had to infer which
artifact was enough proof for each human-only item.

That ambiguity matters most for real MCP client checks, reviewed inbox captures,
maintenance inspection, and TestPyPI publishing because each item has a
different useful evidence shape.

## Decision

Add `suggested_artifacts` to each manual acceptance plan item.

The suggestions are canonical data in `scripts/manual_acceptance.py`, so the
field appears consistently in:

- `ai-dememory acceptance plan --json`
- the human-readable `ai-dememory acceptance plan` output
- read-only MCP `memory.acceptance_plan`
- `manual_acceptance_plan` inside `ai-dememory release-evidence`
- the Markdown release evidence report

The field is advisory. Reviewers still decide whether the attached artifact is
adequate and record final proof with `ai-dememory acceptance record`.

## Benefits

- Reduces ambiguity in the remaining manual v2 release work.
- Keeps release evidence actionable without adding a separate runbook command.
- Lets MCP clients and plugin skills guide reviewers to the right proof while
  preserving CLI-only evidence recording.

## Limitations

- Suggested artifacts do not verify that a check actually passed.
- The guidance is generic enough to cover local environments, so reviewers may
  attach equivalent proof instead of the exact listed artifact.
- It does not complete manual acceptance, publish packages, or merge PRs.

## Future Risks

- If acceptance items are renamed or split, their artifact suggestions must be
  updated in the same change.
- If manual acceptance moves to an external tracker, the tracker schema should
  preserve the same artifact guidance.

## Dependencies

- ADR 0047 defines read-only manual acceptance planning.
- ADR 0048 exposes the plan over MCP.
- ADR 0049 embeds the plan in release evidence.
- `scripts/manual_acceptance.py` remains the source of truth for item ids,
  status, commands, and artifact guidance.
