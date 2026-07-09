# ADR 0069: Plugin MCP Config Smoke

Status: Accepted for the v2 draft.

## Context

ADR 0068 made the Codex plugin MCP tool surface exact and reviewable, but that
guard only inspects the repository artifact. A plugin config can still be
syntactically valid and tool-surface compliant while failing to launch from a
source checkout, especially when maintainers need to verify the checked-in
`plugins/ai-dememory/.mcp.json` before publishing the Python package or
refreshing the plugin marketplace.

The existing `mcp-client-smoke` command already validates generated installed
and Docker client configs by launching the configured stdio server and running
`initialize` plus `ping`. It did not support launching an existing config file
with a temporary command override, which made plugin config smoke require manual
editing or an installed `ai-dememory` command on `PATH`.

## Decision

Extend `mcp-client-smoke --config <file>` with optional launch overrides:

- `--command <executable>` replaces the selected server command
- repeated `--command-arg <arg>` replaces the selected server args with those
  args followed by `mcp --stdio`

When no override is provided, config-file smoke keeps the config unchanged.
Package install smoke now includes a `plugin mcp config smoke` step that
launches `plugins/ai-dememory/.mcp.json` with the installed `ai-dememory`
executable. ADR 0087 later strengthens config-file smoke by verifying
`enabled_tools` against the launched server's `tools/list` response. Release
docs and the v2 checklist include a source-checkout smoke command for the same
plugin config.

## Benefits

- Verifies the checked-in plugin MCP config actually starts a server and
  responds to `initialize` and `ping`.
- Verifies checked-in plugin `enabled_tools` entries against the launched
  server when ADR 0087 behavior is present.
- Lets source checkouts smoke the plugin config through `scripts/ai_dememory.py`
  without editing `.mcp.json`.
- Keeps package smoke aligned with the plugin marketplace artifact.
- Preserves the plugin config environment and enabled-tool allowlist during
  smoke.

## Caveats

- The smoke proves launch and protocol basics, not full Codex plugin
  installation or client marketplace refresh behavior.
- A command override can mask a broken `command` field in the plugin config, so
  release checks still inspect the static command shape separately.
- The package smoke must run from a distribution checkout where
  `plugins/ai-dememory/.mcp.json` is present.

## Future Risks

- If Codex plugin MCP config semantics diverge from generic MCP client config,
  the smoke may need a client-specific adapter.
- If the plugin config gains multiple servers, the smoke must keep using an
  explicit server name to avoid launching an unintended server.
- If plugin install UX later supports Docker mode directly, the checked-in
  plugin config may need separate installed and Docker smoke profiles.

## Dependencies

- ADR 0014 defines generated MCP client config smoke.
- ADR 0018 defines expanded package install smoke coverage.
- ADR 0068 defines the plugin MCP tool-surface guard.
- `scripts/mcp_client_smoke.py` remains the shared MCP client launch smoke.
- `plugins/ai-dememory/.mcp.json` remains the Codex plugin MCP config artifact.
