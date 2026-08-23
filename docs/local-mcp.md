# Local MCP Server Setup

Use MCP when an AI client such as Codex or Claude needs local memory tools.
The server uses stdio, not a network port, and its configuration binds the
installed `ai-dememory` command to one private vault through
`AI_DEMEMORY_ROOT`.

This is an optional integration after installation. The public source repository
contains demo/validation fixtures only; it is never the vault to connect.

## User Path: Install, Create A Vault, Then Connect A Client

Published stable 2.1.0 is the PyPI release. Its historical wizard compatibility
argument is required only for this stable package:

```bash
pipx install ai-dememory==2.1.0
ai-dememory init ~/code/my-memory --wizard --require-version 2.1.0
```

Generate a fragment only for a client you intend to connect. Read it and copy it
into that client's configuration yourself; the command never edits Codex,
Claude, or another host automatically.

```bash
ai-dememory --root ~/code/my-memory mcp-config --client codex
```

On Windows, use a private path such as `D:\Memory\my-vault` in place of the
example. The produced Codex fragment belongs in `~/.codex/config.toml` or a
trusted project's `.codex/config.toml`; Claude and generic clients receive their
native JSON shape. Full field examples are in
[MCP client configuration](mcp-client-config.md).

The current TestPyPI prerelease `2.1.1rc2` is an evaluation route, not a PyPI
upgrade. After its exact install from [Installation](install.md), use the
shorter wizard-first command `ai-dememory init ~/code/my-memory --wizard`.
Prerelease-generated MCP configuration omits the legacy stable pin. The earlier
`2.1.1rc1` prerelease is historical evidence, not a second recommended route.

## What The Generated Fragment Protects

Generated private-vault configuration defaults to the server-enforced four-tool
`core` profile, an explicit root binding, and a bounded idle lease. Codex also
receives a matching `enabled_tools` allowlist as defense in depth. Use
`--profile working` or `--profile review` only when that extra capability is
needed. `--profile admin` retains the full historical server surface for broad
maintenance and compatibility; it is not the default.

The default `balanced` idle lease is 600 seconds; wizard intensities emit
120/600/1800 seconds for `minimal`/`balanced`/`active`. An idle client can
reconnect later. Set `--idle-timeout-seconds 0` only when an external
supervisor owns lifecycle cleanup.

The server closes cleanly on stdin EOF. Package-owned children run with closed
stdin, bounded deadlines, and an owned process group/tree: Windows uses a
kill-on-close Job Object and POSIX uses a separate session/process group. These
controls cover ai-dememory children, not unrelated browser, Node, Python, or
plugin processes owned by the host application.

## Optional Configuration Check

After copying a fragment into a real client, an advanced diagnostic can launch
the configured installed CLI and verify `initialize` and `ping`. It is not a
first-run requirement:

```bash
ai-dememory --root ~/code/my-memory dev mcp-client-smoke
```

When upgrading an existing stable installation, regenerate the fragment for
each vault before replacing the previous host entry:

```bash
pipx install --force ai-dememory==2.1.0
ai-dememory --root ~/code/my-memory mcp-config --client codex
```

If a host package or Docker image came from a release candidate or mutable
checkout, rebuild it with the exact stable package first.
`ai-dememory version-check 2.1.0` remains a CI/support diagnostic, not a setup step.

## Docker: Local Stdio Only

Docker is an optional local stdio transport. It does not expose a port or turn
MCP into a remote service. Build the image from a trusted source checkout, then
generate the client configuration for an already initialized private vault:

```bash
docker build -t ai-dememory:local .
ai-dememory mcp-config --client codex --mode docker --root ~/code/my-memory
```

The generated configuration owns the exact mount, image, profile, root binding,
and idle lease; this guide intentionally does not provide a raw `docker run`
recipe. It binds the selected vault at `/memory` and appends
`mcp --stdio --idle-timeout-seconds 600 --profile core --require-bound-root`.
Do not expose the container as a network service without a separate
authentication, authorization, and privacy design.

## Maintainer Checkout Recipe

The following source-checkout form exists for development and CI diagnostics.
It is not an installation path and must never point at the public repository as
a vault:

```bash
python3 scripts/ai_dememory.py --root /path/to/private-vault mcp-config --client codex \
  --command python3 \
  --command-arg /path/to/ai-dememory/scripts/ai_dememory.py
python3 scripts/ai_dememory.py --root /path/to/private-vault mcp-client-smoke \
  --command python3 \
  --command-arg /path/to/ai-dememory/scripts/ai_dememory.py
```

## REST Instead Of MCP

Use MCP stdio for AI clients. For local dashboards or scripts that need HTTP,
use the separate loopback [Local REST API](local-api.md).
