# ADR 0181: Setup Health Context Config

Status: Accepted

## Context

ADR 0156 made `ai-dememory context` and MCP `memory.context` read optional
vault-local `[context]` defaults from `.ai-dememory.toml`. Invalid values fall
back to safe built-in defaults, which is good for runtime resilience but weak for
setup diagnostics: users can think they configured auto context while the tool is
quietly using defaults.

`setup health` is the read-only local setup surface for plugin and MCP clients,
so it is the right place to expose this configuration state.

## Decision

Add a `context_config` object to `ai-dememory setup health --json` and MCP
`memory.setup_health`.

The object reports:

- whether a `[context]` section is configured;
- the effective `default_budget_tokens`, `include_working_memory`, and
  `explain_results` values;
- whether each value came from config, a default, an invalid-value fallback, or
  a min/max clamp;
- validation errors for invalid or clamped values; and
- next actions when local config needs review.

The diagnostic is read-only. It does not write `.ai-dememory.toml`, rebuild
indexes, read provider files, or change working memory.

## Benefits

- Setup flows can show when context defaults are active or silently falling
  back.
- Plugin skills can guide users to fix `.ai-dememory.toml` before relying on
  auto context.
- MCP clients get the same setup signal as the CLI.
- Runtime context assembly keeps the safe fallback behavior from ADR 0156.

## Limitations

- The status covers only the current scalar `[context]` settings.
- It does not validate future context profiles or per-client presets.
- It does not check context output quality; recall fixtures remain the quality
  benchmark.

## Future Work

- Add profile validation if context profiles are introduced.
- Include client-specific preset diagnostics after real MCP client usage shows a
  stable need.
- Consider a config-wide setup-health section if more config areas need the same
  default/fallback visibility.

## Dependencies

- ADR 0153 defines setup health as a read-only local setup surface.
- ADR 0156 defines context config defaults and fallback behavior.
- ADR 0179 adds validation status to setup health.
- ADR 0180 adds recall review status to setup health.
- `scripts/context_memory.py` owns context defaults.
- `scripts/setup_plan.py` owns setup health assembly.
