# ADR 0022: Local REST API Smoke

## Status

Accepted for v2 draft.

## Context

The v2 checklist requires the local REST API to serve loopback health, search,
and graph endpoints, and to refuse unauthenticated non-loopback binds. The API
already had unit coverage, but there was no first-class CLI smoke command that
release checks, CI, package install smoke, and maintainers could run directly.

The REST API is not a remote service for v2. It exists for local tools that
cannot launch MCP stdio but can call localhost.

## Decision

Add `ai-dememory api-smoke`, backed by `scripts/api_smoke.py`.

The smoke uses a temporary vault, starts the API on an ephemeral loopback port,
and verifies:

- unauthenticated requests are rejected when an API key is configured
- `/health`, `/search`, `/graph`, and `/memories/{id}` work on loopback
- sensitive memories are excluded by default
- `/proposals` writes only to `inbox/llm-captures/`
- `/reindex` rebuilds the local SQLite index
- `ai-dememory api --host 0.0.0.0` refuses startup without
  `AI_DEMEMORY_API_KEY` or an explicit unsafe override

Wire the smoke into CI and package install smoke. Keep `release-check`
dependency-light and non-server-starting, but require the smoke script and ADR
to exist.

## Benefits

- Converts local REST API release checklist items into executable evidence.
- Exercises the installed CLI path through package smoke.
- Verifies the local-first network safety default before release.
- Keeps the smoke self-contained and disposable through a temporary vault.

## Limitations

- It does not test concurrent clients or long-running API operation.
- It does not prove firewall configuration or production network safety.
- It does not make the API remote-ready; remote auth/OAuth remains out of scope.
- It validates representative endpoints, not every possible query parameter.

## Future Risks

- If new API endpoints are added, the smoke should grow to cover their safety
  boundaries.
- If the API moves to another server framework, this smoke should continue to
  run through the public CLI contract.
- Network policy changes could require stronger authentication checks before
  any non-loopback use is allowed.
