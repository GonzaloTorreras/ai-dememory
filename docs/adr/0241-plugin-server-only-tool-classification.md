# ADR 0241: Plugin Server-only Tool Classification

Status: Superseded by ADR 0249 for the default profile; retained as historical
classification context.

## Context

The MCP server exposes the full local memory surface, while the Codex plugin
ships a default `enabled_tools` allowlist for review-first workflows. The server
had 74 tools and the plugin enabled 67. The difference was deliberate,
but release evidence only reported the two counts. That made it easy for docs or
skills to recommend a broad execution tool as plugin-default even when the
checked-in plugin config did not expose it.

## Decision

The historical decision was to classify every MCP tool in release checks as
either plugin-enabled or server-only:

- plugin-enabled, listed in `EXPECTED_PLUGIN_MCP_TOOLS`; or
- server-only, listed in `EXPECTED_PLUGIN_MCP_SERVER_ONLY_TOOLS`.

The current server-only tools are:

- `memory.reindex`
- `memory.consolidate`
- `memory.secret_scan`
- `memory.mark_seen`
- `memory.import_chats`
- `memory.maintenance_run`
- `memory.sleep_apply_reviewed`

ADR 0249 replaces the two-way default split with `core`, `working`, `review`,
and `admin` profiles. The release guard still classifies every non-core tool as
server-only by default and validates the narrower plugin allowlist.

`release-check` now fails if a server tool is unclassified, if a classified tool
does not exist in the server inventory, if plugin-enabled and server-only
classifications overlap, or if `docs/codex-plugin.md` omits the server-only
boundary.

## Benefits

- Keeps the plugin install surface explicit and reviewable.
- Prevents future MCP tools from silently bypassing the plugin boundary review.
- Gives plugin skills a clear rule: prefer read-only planning/status tools, then
  ask for explicit CLI commands for broad local actions.
- Makes the difference between full MCP server users and default plugin users
  visible in user-facing docs.

## Limitations

- The classification is static and must be updated whenever an MCP tool is
  added, renamed, or removed.
- Server-only does not mean unsafe; it means the tool has broader local effects
  than the default plugin workflow should expose automatically.
- Direct MCP clients can still choose to enable the full server surface.

## Future Risks

- If Codex plugins support per-tool risk metadata, this static split should
  migrate to richer machine-readable approval classes.
- If plugin users need routine access to one server-only tool, add it through a
  separate ADR that updates the allowlist, docs, skills, and smoke tests
  together.
- If maintenance/import flows become more granular, some server-only tools may
  split into read-only preview tools and approval-gated apply tools.

## Dependencies

- ADR 0068 defines the plugin MCP tool surface guard.
- ADR 0087 defines config-file `enabled_tools` verification.
- ADR 0133 defines the scheduler and plugin blueprint.
- `plugins/ai-dememory/.mcp.json` remains the plugin allowlist source.
- `scripts/release_check.py` owns the classification guard.
