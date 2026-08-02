# ADR 0249: MCP tool profiles and maintainer CLI namespace

## Status

Accepted on 2026-07-11. Server enforcement was added by ADR 0257 on
2026-07-26; ADR 0256 added the stricter checked-in public profile.

## Context

The MCP server exposes 74 tools and the previous plugin allowed 67. Serialized
tool schemas could consume substantially more model context than the default
2,000-token memory payload. The public CLI also mixed routine vault commands
with CI, distribution, release, and publishing guards in one long help page.

## Decision

Keep the complete server contract, but define additive client profiles:
`public`, `core` (private-vault default), `working`, `review`, and explicit
unfiltered `admin`. Generated private-vault configs use the four-tool `core`;
the bundled public plugin uses the three-tool `public` profile. The selected
profile is passed to the server, which filters
`tools/list` and rejects out-of-profile calls; Codex `enabled_tools` remains an
additional client-side reduction. Inventory output reports exact compact-schema
bytes and a transparent bytes/4 token estimate per profile.

Group maintainer commands under `ai-dememory dev`. Keep their historical
top-level forms as compatibility aliases, but hide those aliases from normal
help so user workflows remain foregrounded.

## Safety invariants

- Profiles never remove tools from the explicit `admin` compatibility contract.
- `admin` is explicit and preserves the unfiltered backwards-compatible server.
- `public`, `core`, `working`, and `review` may reference only tools in
  `tools/list`.
- The plugin allowlist must exactly match `public` and contain no duplicates.
- Generated configs bind a vault and pass the selected profile to the server.
- Resources and prompts are available only under explicit `admin`.
- Profiles do not weaken tool-level path, trust, review, or secret controls.

## Consequences

Every generated client spends far less prompt context on the default tool
surface, including clients without a native allowlist. Advanced workflows opt
into a broader server profile. Existing scripts using direct maintainer
commands continue to work while new documentation uses the `dev` namespace.

## Dependencies

- Native Codex MCP TOML supports `enabled_tools`.
- Plugin MCP configuration supports the same allowlist field.
- The MCP inventory can load the canonical server tool definitions.
- ADR 0257 defines the server-enforced capability and resource boundary.

## Limitations

Profiles reduce the advertised and callable MCP surface, but they do not replace
tool-level authorization, path validation, review gates, or secret controls.
Direct invocation without an explicit profile retains the `admin`
compatibility default; generated configs always pass a profile and require an
explicitly bound vault. The bytes/4 token estimate is useful for comparisons but
is not tied to one model tokenizer.

## Future Risks

New tools may fit more than one profile or make a profile too large. Inventory,
plugin, and release guards must fail on drift, and maintainers should measure
schema cost before adding a default tool.
