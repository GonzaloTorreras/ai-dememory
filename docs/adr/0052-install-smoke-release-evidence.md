# ADR 0052: Install Smoke Release Evidence

Status: Accepted for the v2 draft.

## Context

`memory.release_evidence` is intentionally available only when the MCP root is
the distribution checkout. Installed packages usually run against private
memory vaults, where release evidence for the tool repository should not be
invented.

The package install smoke already creates a fresh vault and exercises installed
CLI, MCP config, and MCP `initialize`/`ping` behavior. It did not verify the
new release-evidence MCP tool's plain-vault response.

## Decision

Extend package install smoke to call:

```bash
ai-dememory mcp --call memory.release_evidence --args "{}"
```

from the temporary fresh vault. The smoke requires the JSON response to include
`available=false`, `evidence=null`, and a reason that mentions the distribution
checkout requirement.

This is a negative-path smoke. Distribution-checkout release evidence remains
covered by `release-evidence`, `release-check`, and MCP runtime smoke in the
repository checkout.

## Benefits

- Proves the installed MCP surface includes `memory.release_evidence`.
- Confirms plain vaults get a clear unavailable response instead of repository
  release evidence.
- Keeps package install smoke aligned with the MCP tool inventory.

## Limitations

- The smoke does not run full release evidence from an installed wheel against a
  cloned distribution checkout.
- It does not verify real GitHub CI, TestPyPI, PyPI, or GUI MCP clients.
- Docker smoke continues to verify local MCP runtime behavior separately.

## Future Risks

- If release evidence gains a packaged-data fallback, this negative-path
  assertion may need to distinguish vault roots from installed distribution
  metadata.
- If MCP availability checks change from git checkout detection to a profile
  detector, the expected reason text should stay stable enough for install
  smoke users to diagnose the issue.

## Dependencies

- ADR 0051 defines `memory.release_evidence` and its plain-vault response.
- ADR 0043 defines installed and Docker doctor summary smoke coverage.
- `scripts/install_smoke.py` remains the reusable install smoke runner.
