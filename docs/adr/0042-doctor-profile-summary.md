# ADR 0042: Doctor Profile Summary

## Status

Accepted for the v2 draft.

## Context

ADR 0041 made doctor checks profile-aware so vault roots skip
distribution-only MCP contract validation. That fixed first-run vault behavior,
but the selected profile was implicit. Users and MCP clients could see which
checks ran only by inferring from the row names.

## Decision

Expose doctor profile information without breaking existing row-oriented output:

- keep `ai-dememory doctor --json` as the existing list of check rows;
- add `ai-dememory doctor --json --summary` with `profile`, `summary`, and
  `checks`;
- add a text summary line when `ai-dememory doctor --summary` is used;
- include `profile` in MCP `memory.doctor` output.

Profiles are `distribution`, `vault`, or `unknown`.

## Benefits

- Makes profile-aware doctor behavior visible to users and MCP clients.
- Preserves backwards compatibility for existing JSON consumers.
- Gives release evidence and troubleshooting flows a compact status summary.

## Limitations

- The summary reports current local state only.
- The profile remains based on simple marker files.
- Existing `doctor --json` output remains row-only, so callers must opt in to
  the summary object.

## Future Risks

- Additional profiles may require client UI changes.
- If consumers assume MCP `memory.doctor` only returns `checks` and `summary`,
  the new `profile` field should still be tolerated by structured clients.
- If profile detection becomes configurable, summaries must include the chosen
  source of that configuration.

## Dependencies

- ADR 0040 exposes doctor status over MCP.
- ADR 0041 defines vault versus distribution doctor profile behavior.
- ADR 0031 requires new ADRs to document tradeoffs and dependencies.
