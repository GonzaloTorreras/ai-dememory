# ADR 0060: Working Status Summary

Status: Accepted for the v2 draft.

## Context

Phase 2 of the v2 memory plan adds generated working memory snapshots and
handoffs under `working/`. The CLI and MCP server already support writing
`working/current.json`, `working/recent-session.md`, and Markdown handoffs under
`working/handoffs/`.

Before this ADR, users and MCP clients had to read current state and handoff
files separately. That made resume workflows harder because there was no single
read-only summary of whether current state existed, whether a recent-session
file existed, and which handoffs were available.

## Decision

Add a shared working status summary:

- CLI: `ai-dememory working status --json`
- MCP: `memory.working_status`

The status summary reports:

- whether `working/current.json` exists and its parsed content when valid JSON
- whether `working/recent-session.md` exists
- total handoff count
- recent handoff summaries, bounded by a caller-provided limit

The MCP tool is read-only and has bounded `limit` input. The package install
smoke runs `working status --json` so installed CLI distributions keep this
resume surface available.

## Benefits

- Gives users and clients a single resume-oriented view of generated working
  state.
- Keeps status inspection separate from writing snapshots or handoffs.
- Makes plugin skills less likely to over-read arbitrary files under
  `working/`.

## Limitations

- Working state remains generated operational context, not durable reviewed
  memory.
- The status command does not validate whether handoff notes are factually
  correct.
- Invalid `working/current.json` is treated as missing parsed current state
  rather than failing the whole status command.

## Future Risks

- If working handoffs become large or numerous, the summary may need pagination
  rather than a simple bounded recent list.
- If generated working state gains a schema version, the status output should
  include that version and validation status.

## Dependencies

- ADR 0038 defines MCP working memory tools and their generated-state boundary.
- ADR 0039 defines the Codex plugin working-session skill.
- `scripts/working_memory.py` remains the shared implementation for CLI and MCP
  working state operations.
