# ADR 0039: Codex Plugin Working Session Skill

## Status

Accepted for the v2 draft.

## Context

ADR 0038 added MCP tools for generated working snapshots and handoffs. The
Codex plugin already bundled setup, recall, review, and maintenance skills, but
it did not give Codex a dedicated trigger for session-state workflows. Without a
skill, agents could ignore the working-memory tools or treat generated working
state as if it were durable memory.

## Decision

Add a `memory-working-session` plugin skill. The skill instructs Codex to:

- read `memory.working_current` before resuming stateful work when useful;
- call `memory.working_snapshot` after meaningful task steps or before
  interruption;
- call `memory.working_handoff` for pause, handoff, or continuation requests;
- treat generated working files as operational state, not canonical fact;
- fall back to the `ai-dememory working` CLI commands when MCP is unavailable.

The release check now requires this skill in the plugin bundle, and the release
checklist names the working-session skill as part of the v2 plugin surface.

## Benefits

- Makes the newly exposed MCP working-memory tools discoverable in Codex.
- Keeps generated handoffs separate from durable memory promotion.
- Gives future agents a clear workflow for resume and handoff scenarios.

## Limitations

- The skill does not install hooks or run background capture.
- The skill cannot verify that a handoff is factually correct; the next agent
  must still inspect repository and PR state.
- Working snapshots remain single-note summaries rather than structured task
  graphs.

## Future Risks

- If working-state retention grows, the plugin may need a pruning or review
  skill.
- If clients add richer session lifecycle hooks, this skill may need event-level
  guidance for automatic snapshot timing.
- Agents may still overuse handoffs unless review-first wording stays explicit.

## Dependencies

- ADR 0038 defines the MCP working-memory tools used by this skill.
- ADR 0005 and ADR 0006 keep hook capture opt-in and review-first.
- ADR 0031 requires new ADRs to document tradeoffs and dependencies.
