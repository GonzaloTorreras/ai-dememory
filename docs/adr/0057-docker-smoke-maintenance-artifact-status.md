# ADR 0057: Docker Smoke Maintenance Artifact Status

Status: Accepted for the v2 draft.

## Context

ADR 0055 added generated artifact visibility to maintenance status, and ADR
0056 added package install smoke coverage for the installed CLI path. Docker is
the reproducible local MCP path, but Docker smoke did not validate that the
container exposes the same `maintenance status` artifact map for a bind-mounted
vault.

## Decision

Extend Docker smoke to run:

```bash
docker run --rm -v <temp-vault>:/memory -e AI_DEMEMORY_ROOT=/memory \
  ai-dememory:local maintenance status
```

after the mounted vault has been initialized and indexed. The smoke validates
that the generated artifact map includes index, graph, weights, lifecycle score
JSON, and lifecycle report entries with the expected field types.

## Benefits

- Keeps Docker and installed CLI setup paths aligned for maintenance
  visibility.
- Verifies local Docker users can inspect generated artifact state without
  running a separate host CLI.
- Catches image packaging drift for the maintenance status surface.

## Limitations

- The check requires Docker and only runs where Docker is available.
- It validates status shape, not semantic freshness or report contents.
- It does not install scheduler jobs; Docker scheduling remains host-owned and
  opt-in.

## Future Risks

- New generated artifacts must be reflected in Docker smoke and the shared
  maintenance status validator.
- Platform-specific mount syntax may need special handling for future Docker
  client environments.

## Dependencies

- ADR 0044 defines generated Docker MCP client config smoke coverage.
- ADR 0055 defines generated artifact visibility in maintenance status.
- ADR 0056 defines installed package smoke coverage for the same status shape.
- `scripts/install_smoke.py` remains the shared package and Docker smoke
  runner.
