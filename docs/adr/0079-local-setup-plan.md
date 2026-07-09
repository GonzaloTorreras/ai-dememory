# ADR 0079: Local Setup Plan

Status: Accepted for the v2 draft.

## Context

The v2 install path is intentionally split into passive package/plugin
installation and explicit user-approved local setup. Users still need to stitch
together several commands after install: doctor, index, MCP config, provider
setup, hook config, scheduler dry-run, maintenance, and manual acceptance
planning.

That split is safe, but it creates friction for first-run setup and Codex plugin
skills. A setup helper must not become an installer that configures providers,
writes client configs, installs hooks, installs schedules, imports chats, or
records manual acceptance evidence automatically.

## Decision

Add `ai-dememory setup plan`.

The command returns reviewable command arrays for vault health, indexing, graph
generation, MCP config generation, provider setup planning, hook config/dry-run,
scheduler dry-run, maintenance profiles, and manual acceptance planning. It also
embeds the read-only provider setup plan.

Expose the same read-only contract over MCP as `memory.setup_plan` and enable it
in the Codex plugin MCP surface. The tool reports explicit side-effect flags:
`mutates_system=false`, `writes_files=false`, `reads_provider_files=false`,
`writes_import_candidates=false`, `installs_schedules=false`, and
`installs_hooks=false`.

## Benefits

- Gives users one command to understand first-run local setup without changing
  their machine.
- Gives Codex plugin skills a structured plan instead of hard-coded prose.
- Keeps provider, hook, scheduler, and manual acceptance actions review-first.
- Makes the install UX easier to smoke-test through the packaged CLI and MCP.

## Limitations

- The plan returns commands but does not validate that every external client can
  consume the generated config.
- It does not write config files or install scheduler jobs; users must still run
  approved setup commands.
- Provider path existence is a hint only and does not validate provider export
  schemas.

## Future Risks

- If client config formats change, the setup plan may need client-specific next
  actions rather than generic command arrays.
- If setup becomes interactive later, it must preserve the no-side-effect dry
  plan as the default path.
- If remote MCP or hosted import workflows are added, this local setup plan must
  remain explicit about credential and network boundaries.

## Dependencies

- ADR 0005 defines hook provider config boundaries.
- ADR 0014 defines generated MCP client config smoke.
- ADR 0026 defines Docker maintenance schedule planning.
- ADR 0066 defines read-only MCP scheduler status.
- ADR 0078 defines read-only provider setup planning.
- `scripts/setup_plan.py` is the executable setup-planning contract.
