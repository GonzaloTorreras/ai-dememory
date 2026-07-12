# ADR 0249: MCP tool profiles and maintainer CLI namespace

## Status

Accepted on 2026-07-11.

## Context

The MCP server exposes 74 tools and the previous plugin allowed 67. Serialized
tool schemas could consume substantially more model context than the default
2,000-token memory payload. The public CLI also mixed routine vault commands
with CI, distribution, release, and publishing guards in one long help page.

## Decision

Keep the complete server contract, but define additive client profiles:
`core` (default), `working`, `review`, and explicit unfiltered `admin`.
Generated Codex TOML and the bundled plugin use the seven-tool `core` allowlist.
Inventory output reports exact compact-schema bytes and a transparent bytes/4
token estimate per profile.

Group maintainer commands under `ai-dememory dev`. Keep their historical
top-level forms as compatibility aliases, but hide those aliases from normal
help so user workflows remain foregrounded.

## Safety invariants

- Profiles never remove tools from the MCP server contract.
- `admin` is explicit and preserves the unfiltered backwards-compatible server.
- `core`, `working`, and `review` may reference only tools in `tools/list`.
- The plugin allowlist must exactly match `core` and contain no duplicates.
- Profiles do not weaken tool-level path, trust, review, or secret controls.

## Consequences

Clients that honor `enabled_tools` spend far less prompt context on the default
tool surface. Advanced workflows opt into a broader profile. Existing scripts
using direct maintainer commands continue to work while new documentation uses
the `dev` namespace.

## Dependencies

- Native Codex MCP TOML supports `enabled_tools`.
- Plugin MCP configuration supports the same allowlist field.
- The MCP inventory can load the canonical server tool definitions.

## Limitations

Profiles are client exposure policy, not server authorization. Clients that do
not support allowlists still receive all 74 tools. The bytes/4 token estimate is
useful for comparisons but is not tied to one model tokenizer.

## Future Risks

New tools may fit more than one profile or make a profile too large. Inventory,
plugin, and release guards must fail on drift, and maintainers should measure
schema cost before adding a default tool.
