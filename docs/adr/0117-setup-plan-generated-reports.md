# ADR 0117: Setup Plan Generated Reports

## Status

Accepted.

## Context

The first-run setup planner already gives users and MCP clients a read-only
checklist for local setup. As release readiness added generated recall review,
recall review packet, and manual acceptance report artifacts, users still had to
discover those handoff commands from separate docs.

The setup planner must remain passive. It should not write reports, install
hooks, install schedules, read provider chat files, import chats, or record
manual acceptance evidence automatically.

## Decision

Add a `generated_reports` command group to `ai-dememory setup plan --json` and
MCP `memory.setup_plan`.

The group contains command arrays for:

- `recall-fixtures review-plan --write-report`
- `recall-fixtures packet --write-report`
- `acceptance plan --write-report`
- `acceptance packet --write-report`
- `hooks captures --write-report`
- `release-evidence --write-report`

The setup plan also exposes `suggests_generated_reports=true` to make the
boundary explicit: the planner suggests commands, but does not execute them or
write files.

## Benefits

- Gives first-run users one place to find review and release handoff report
  commands.
- Keeps Codex plugin skills from hard-coding generated-report command names.
- Preserves the review-first setup contract while making handoff artifacts more
  discoverable.

## Limitations

- Suggested report commands may still fail if the vault is not ready or if
  generated report content is rejected by secret scanning.
- The setup plan does not decide when reports are required; reviewers still
  choose when to generate them.
- The command group does not create timestamped report paths.
- ADR 0217 adds a separate generated archive status command group; archive
  inspection remains read-only and separate from report writing.

## Future Risks

- If generated report commands gain required options, setup-plan command arrays
  must stay in sync.
- If report artifacts move outside `reports/`, install and release docs must be
  updated together.
- If setup becomes interactive, the read-only plan must remain the default
  contract.

## Dependencies

- ADR 0079 defines the local setup planner.
- ADR 0115 defines the recall review plan report.
- ADR 0116 defines the manual acceptance plan report.
- ADR 0186 defines the manual acceptance packet.
- ADR 0187 defines the recall review packet.
- ADR 0217 defines setup-plan generated archive status commands.
- `scripts/setup_plan.py` owns the setup-plan command schema.
- MCP `memory.setup_plan` returns the same setup-plan payload.
