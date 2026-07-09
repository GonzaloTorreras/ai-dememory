# ADR 0067: MCP Provider Status

Status: Accepted for the v2 draft.

## Context

The v2 memory workflow supports optional provider imports from local Codex,
Claude, ChatGPT, Cursor, and Windsurf folders. Imports are review-first:
configured provider imports write candidates under `inbox/imports/<provider>/`
and never promote durable memory directly.

MCP clients already had `memory.providers_detect` to find likely local provider
folders and `memory.import_chats` to perform an approved import. They could also
infer configured provider state from `memory.maintenance_status`, but that
payload is broad and focused on maintenance. Plugin setup flows need a focused
read-only answer to: which providers are configured, which are enabled, and
which are ready to import if the user approves.

## Decision

Expose `memory.providers_status` as a read-only MCP tool.

The tool returns:

- `providers`
- `configured_count`
- `enabled_count`
- `import_ready_count`
- `mutates_system`

Each provider row includes the provider name, configured path, existence,
configured/enabled booleans, `import_ready`, and a short readiness reason. The
tool reads `.ai-dememory.toml` provider settings and checks path existence. It
does not read provider chat files, scan provider contents, configure providers,
write import candidates, or run maintenance.

## Benefits

- Gives MCP clients and Codex plugin skills a direct provider setup diagnostic.
- Keeps import approval separate from readiness inspection.
- Avoids overloading `memory.maintenance_status` for provider-specific setup
  UX.
- Makes provider import readiness visible in runtime smoke without touching
  external provider folders.

## Limitations

- Path existence is only a readiness hint. It does not prove the provider folder
  contains useful, supported, or non-secret chat files.
- The tool does not validate provider export formats; actual import still
  performs rendering and secret scanning.
- Disabled providers remain visible so clients can explain why imports will not
  run, but clients must not treat visibility as approval to import.

## Future Risks

- If provider import schemas grow provider-specific validation, the status rows
  may need per-provider readiness details.
- If provider paths can contain sensitive usernames or workspace names, clients
  should avoid sending this payload to remote services.
- If background import scheduling is added later, provider readiness must remain
  separate from scheduler installation and import execution.

## Dependencies

- ADR 0007 defines import and capture review boundaries.
- ADR 0026 defines Docker-backed local maintenance planning.
- ADR 0055 defines broad maintenance status visibility.
- `scripts/provider_import.py` remains the shared provider detection, status,
  configuration, and import implementation.
