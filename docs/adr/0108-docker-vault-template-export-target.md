# ADR 0108: Docker Vault Template Export Target

## Status

Accepted.

## Context

Docker smoke bind-mounts a host temporary directory at `/template` and runs
`ai-dememory vault-template export /template --json` inside the container. The
exported files are expected to appear on the host bind mount, but the JSON
payload correctly reports the path requested inside the container.

The smoke originally compared the JSON `target` value to the host temporary
path. That works for installed CLI smoke, but fails for Docker because the
container reports `/template` while the host checks files under the bind-mounted
temporary directory.

## Decision

Allow `assert_vault_template_export` to receive an explicit expected reported
target. Installed CLI smoke keeps comparing JSON `target` to the resolved host
path. Docker smoke passes `/template` as the expected reported target and still
verifies that the required template files exist on the host bind mount.

## Benefits

- Keeps Docker smoke aligned with the actual container path contract.
- Continues verifying host bind-mounted template files instead of trusting JSON
  output alone.
- Fixes CI Docker smoke without weakening installed CLI template export checks.

## Limitations

- The assertion still assumes Docker smoke uses `/template` as the container
  mount path.
- It does not prove arbitrary bind-mount paths; it covers the documented local
  Docker MCP smoke command.

## Future Risks

- If Docker smoke changes the template mount point, the expected reported target
  must change with it.
- If the CLI starts normalizing or rewriting reported paths, both installed and
  Docker smoke assertions must be revisited.

## Dependencies

- ADR 0073 defines the vault template export command.
- ADR 0075 defines Docker smoke coverage for vault template export.
- `scripts/install_smoke.py` remains the shared installed package and Docker
  smoke implementation.
