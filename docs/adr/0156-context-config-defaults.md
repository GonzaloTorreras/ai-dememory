# ADR 0156: Context Config Defaults

Status: Accepted

## Context

The v2 operational loop needs token-budgeted context assembly to be repeatable
across CLI, MCP clients, and packaged vault templates. The vault template
already includes a `[context]` section in `.ai-dememory.toml`, but
`ai-dememory context` and MCP `memory.context` still used hard-coded defaults
unless every caller passed explicit arguments.

## Decision

Make context assembly read vault-local `[context]` defaults:

- `default_budget_tokens`
- `include_working_memory`
- `explain_results`

CLI flags and MCP tool arguments take precedence over config. Missing or invalid
config values fall back to safe built-in defaults: a 2000-token budget, working
memory included, and explanation rendering disabled.

Add CLI `context --why` and `context --no-why` for Markdown rendering. JSON
output continues to include per-item `why` metadata, and MCP `memory.context`
accepts `include_working_memory` and `explain_results` arguments.

## Benefits

- New sessions can use stable vault-specific context behavior without repeating
  flags in every client or plugin skill.
- MCP clients can keep config small while still respecting vault policy.
- Explanation rendering remains opt-in for compact context by default.

## Limitations

- The config parser intentionally supports only simple scalar values.
- Context defaults do not change `memory.search`; search explanations remain
  controlled by `search --why` or structured MCP output.
- Token counting remains approximate.

## Future Work

- Add context profiles if users need separate defaults for session start,
  handoff, review, and maintenance workflows.
- Include context default validation in setup health if invalid local config
  becomes common.
- Consider per-client context presets after real MCP client usage produces
  enough examples.

## Dependencies

- ADR 0059 defines search match explanations.
- ADR 0063 defines MCP auto-context.
- `.ai-dememory.toml` remains the vault-local configuration file.
