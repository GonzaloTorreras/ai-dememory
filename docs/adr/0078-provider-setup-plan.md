# ADR 0078: Provider Setup Plan

Status: Accepted for the v2 draft.

## Context

The v2 workflow supports optional imports from local provider folders such as
Codex, Claude, ChatGPT exports, Cursor, and Windsurf. `providers detect` shows
likely paths, `providers configure` writes a selected path, and daily
maintenance imports enabled providers as review candidates.

That still left setup agents and MCP clients to translate detection output into
commands themselves. This is error-prone during install because package and
plugin installation must stay passive: they must not configure providers, read
chat files, write inbox candidates, or install scheduled imports without a user
reviewing the selected folders.

## Decision

Add a read-only provider setup plan.

The CLI command `ai-dememory providers plan --json` returns each known
provider, detected or configured path state, readiness reason, next action,
`providers configure` command array, disable command array, and `import-chats`
command array.

Expose the same contract over MCP as `memory.providers_plan`. The MCP tool is
read-only, reports that it does not mutate the system, does not read provider
chat files, and does not write import candidates. The Codex plugin setup skill
uses the plan as a reviewable setup aid before running any configure command.

## Benefits

- Gives users and setup agents exact provider commands after install without
  silently enabling imports.
- Keeps provider setup review-first and explicit about path choice.
- Reduces drift between CLI setup guidance, MCP diagnostics, plugin skills, and
  installed-package smoke coverage.
- Makes provider setup easier to automate later while preserving the no-side-
  effects contract.

## Limitations

- The plan only checks whether candidate paths exist. It does not validate the
  provider's internal export or chat schema.
- It returns command arrays, not shell-escaped one-liners for every shell.
- It does not prompt interactively or write configuration; users must still run
  a configure command after reviewing the path.

## Future Risks

- Provider path strings may reveal local usernames or workspace names, so
  clients should avoid sharing plan output publicly without review.
- If provider schemas become provider-specific, the plan may need richer
  readiness diagnostics.
- If remote or hosted imports are introduced, the plan must stay local-first and
  avoid credential capture.

## Dependencies

- ADR 0007 defines import and capture candidates as review-first inbox writes.
- ADR 0055 defines maintenance visibility for provider state.
- ADR 0067 defines read-only MCP provider status.
- `scripts/provider_import.py` remains the shared provider detection, status,
  planning, configuration, and import implementation.
