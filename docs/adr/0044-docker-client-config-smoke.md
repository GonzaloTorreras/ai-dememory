# ADR 0044: Docker Client Config Smoke

## Status

Accepted for the v2 draft.

## Context

ADR 0014 added `ai-dememory mcp-client-smoke` for generated MCP client
configuration, and ADR 0011 added package and Docker install smoke. The Docker
path still verified only direct `docker run` MCP stdio behavior. That proved
the image could respond to `initialize` and `ping`, but it did not prove the
generated Docker MCP client configuration could launch the same image.

The setup docs ask users to copy generated Docker config into clients that
support command-based MCP servers. Release smoke should exercise that generated
configuration path directly.

## Decision

Extend Docker install smoke to run `mcp-client-smoke --mode docker` after the
direct Docker MCP ping succeeds.

The smoke runner chooses its launcher based on execution context:

- from a source checkout, it invokes `python scripts/ai_dememory.py`;
- from an installed package or vault-only context, it invokes `ai-dememory`.

Both forms pass `--root <temp-vault>`, `--mode docker`, and the tested image
tag so the generated config bind-mounts the same temporary vault at `/memory`.

## Benefits

- Verifies the exact generated Docker config shape used by MCP clients.
- Keeps local Docker support reproducible without adding HTTP ports or remote
  server behavior.
- Covers both source-checkout and installed-package smoke entry points.

## Limitations

- The check still requires Docker to be installed and able to run containers.
- It verifies stdio initialize/ping only; full client UI integration remains a
  manual acceptance item.
- The installed-package fallback assumes `ai-dememory` is on `PATH`, which is
  true for normal `pipx` and `uv tool` installs.

## Future Risks

- If MCP clients require extra Docker flags, the config generator and smoke
  runner must evolve together.
- If the package exposes multiple console commands later, the launcher
  detection may need an explicit override.
- If remote Docker contexts become supported, the bind-mount assumptions in this
  local-only smoke would no longer be sufficient.

## Dependencies

- ADR 0011 defines reusable package and Docker install smoke.
- ADR 0014 defines generated MCP client config smoke.
- ADR 0043 verifies doctor summary behavior in Docker smoke before this client
  config launch.
