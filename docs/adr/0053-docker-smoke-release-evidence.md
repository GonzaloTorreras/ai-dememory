# ADR 0053: Docker Smoke Release Evidence

Status: Accepted for the v2 draft.

## Context

The Docker image is intended for local stdio MCP use with a user vault mounted
at `/memory`. ADR 0052 added installed-package smoke coverage for
`memory.release_evidence` from a plain vault, but Docker smoke only verified
`init`, `doctor`, `index`, MCP `initialize`/`ping`, and generated Docker client
config behavior.

Because Docker is the reproducible local MCP path, it should verify the same
plain-vault boundary for release evidence as the installed CLI path.

## Decision

Extend Docker smoke to run:

```bash
docker run --rm -v <temp-vault>:/memory -e AI_DEMEMORY_ROOT=/memory \
  ai-dememory:local mcp --call memory.release_evidence --args "{}"
```

after the bind-mounted vault is initialized and indexed. The smoke validates
that the response has `available=false`, `evidence=null`, and a reason that
mentions the distribution checkout requirement.

Docker smoke still does not expose HTTP ports or run a remote MCP server.

## Benefits

- Proves the local Docker image exposes the same MCP release-evidence behavior
  as the installed CLI.
- Confirms mounted private vaults do not receive fabricated distribution
  release evidence.
- Keeps Docker smoke aligned with the v2 MCP tool inventory and install docs.

## Limitations

- The check only covers local Docker execution with a bind-mounted vault.
- It does not verify a Docker image running from a distribution checkout mount.
- It does not prove behavior in GUI clients that cannot launch Docker commands.

## Future Risks

- If Docker support gains a distribution-checkout mode, this smoke may need a
  companion positive-path check.
- If Docker mount syntax changes for Windows or WSL-specific flows, the command
  builder may need platform-aware normalization.

## Dependencies

- ADR 0044 defines generated Docker MCP client config smoke coverage.
- ADR 0051 defines the `memory.release_evidence` MCP tool.
- ADR 0052 defines installed-package plain-vault release-evidence smoke
  coverage.
- `scripts/install_smoke.py` remains the shared package and Docker smoke
  runner.
