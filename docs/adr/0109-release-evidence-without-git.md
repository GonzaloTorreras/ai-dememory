# ADR 0109: Release Evidence Without Git

## Status

Accepted.

## Context

`memory.release_evidence` is intended for distribution checkouts, where release
metadata can be assembled from the repository. Local Docker MCP smoke mounts a
private vault at `/memory`, and that vault is not expected to be a Git checkout.

The Docker image is based on `python:3.12-slim` and does not require `git` for
normal local MCP use. When `memory.release_evidence` checked whether the mounted
root was a Git checkout, missing `git` raised `FileNotFoundError` instead of
returning the documented unavailable response.

## Decision

Treat a missing `git` executable the same as a non-Git vault for
`memory.release_evidence` availability checks. The MCP tool returns
`available: false` with the existing distribution-checkout reason instead of
crashing.

Do not add `git` to the Docker image for this milestone. The image remains a
minimal local MCP runtime, and release evidence stays a best-effort distribution
checkout feature.

## Benefits

- Keeps Docker local MCP smoke aligned with the supported private-vault use
  case.
- Avoids adding an unnecessary runtime dependency to the local stdio image.
- Makes `memory.release_evidence` robust for package installs and containers
  where `git` is unavailable.

## Limitations

- Release evidence still requires a real Git checkout when evidence is expected.
- The unavailable response does not distinguish between missing `git` and a
  plain non-Git vault.

## Future Risks

- If release evidence becomes mandatory in containerized release automation,
  the release container should explicitly include `git` or mount a distribution
  checkout.
- If callers need diagnostic precision, the unavailable reason may need a more
  specific machine-readable code.

## Dependencies

- ADR 0075 defines Docker local MCP smoke coverage.
- ADR 0108 defines Docker bind-mounted vault-template target validation.
- `mcp/server/memory_mcp.py` owns the MCP `memory.release_evidence` dispatch.
