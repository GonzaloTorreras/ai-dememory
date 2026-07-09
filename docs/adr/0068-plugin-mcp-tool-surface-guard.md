# ADR 0068: Plugin MCP Tool Surface Guard

Status: Accepted for the v2 draft.

## Context

The Codex plugin ships a `.mcp.json` file that enables a curated subset of the
local MCP server. The plugin docs and skills describe a review-first surface for
recall, working state, maintenance diagnostics, provider setup diagnostics,
manual acceptance, and review workflows.

As the MCP server gained more v2 tools, the plugin config lagged behind the
documented surface. That created a setup risk: users installing the plugin could
read about a tool in `docs/codex-plugin.md` or a bundled skill, but the plugin
would not expose it by default.

## Decision

Keep an exact expected plugin MCP tool list in `scripts/release_check.py`.

`release-check` now validates that:

- `plugins/ai-dememory/.mcp.json` defines the `ai-dememory` MCP server
- `enabled_tools` is a list of strings
- all expected plugin MCP tools are present
- no unexpected plugin MCP tools are enabled
- `enabled_tools` has no duplicates
- `docs/codex-plugin.md` mentions every expected enabled tool

The plugin tool surface includes read-only tools and selected review-first
write tools that create inbox artifacts, working-state artifacts, review-state
receipts, or explicit local review configuration. Destructive or broad
execution tools such as direct maintenance runs and provider imports remain off
the default plugin surface. ADR 0241 makes that exclusion explicit by requiring
every MCP tool to be classified as plugin-enabled or server-only.

## Benefits

- Keeps plugin install UX aligned with the documented v2 tool surface.
- Prevents regressions where new read-only diagnostics are documented but not
  enabled in the plugin.
- Makes plugin MCP scope reviewable during release checks.
- Keeps more dangerous tools opt-in while still exposing review-first workflows.

## Limitations

- The expected tool list is intentionally static and must be updated whenever
  the plugin surface changes.
- The guard does not prove that a Codex client has installed or refreshed the
  plugin; it validates only the repository artifact.
- Prompt-gated enabled tools still rely on client-side approval behavior.

## Future Risks

- If Codex plugin manifests gain richer per-tool approval metadata, this guard
  should validate that metadata instead of a single flat list.
- If the MCP server splits tools by capability group, the plugin surface may
  need separate profiles for read-only, review-write, and maintenance modes.
- If tool names are renamed, the guard will fail until docs, skills, and plugin
  config are migrated together.

## Dependencies

- ADR 0039 defines the Codex plugin working-session skill.
- ADR 0066 defines read-only scheduler status.
- ADR 0067 defines read-only provider status.
- ADR 0241 defines the plugin server-only MCP tool classification.
- `plugins/ai-dememory/.mcp.json` remains the plugin MCP server config.
- `docs/codex-plugin.md` remains the user-facing plugin tool surface
  documentation.
