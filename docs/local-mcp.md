# Local MCP Server Setup

Use MCP when an AI client such as Codex or Claude needs local memory tools.
The server uses stdio, not a network port, and its configuration binds the
installed `ai-dememory` command to one private vault through
`AI_DEMEMORY_ROOT`.

This is an optional integration after installation. The public source repository
contains demo/validation fixtures only; it is never the vault to connect.

## User Path: Install, Create A Vault, Then Connect A Client

2.1.1 is source release preparation, not an installable route until tag-bound PyPI publication and external readback complete. 2.1.0 is the currently published PyPI compatibility route while release verification is pending.

The published stable 2.1.0 package is the only user-installable route in this
interim state.

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

Regenerate the fragment from the exact published package rather than treating a
source checkout or release candidate as a fallback. Version diagnostics are for
CI or support work, not setup.

## Docker Is Deferred During This Pending Release

The Dockerfile supports a future local stdio transport, but its image must be
built from a source checkout. While 2.1.1 has not completed tag-bound PyPI
publication and external readback, telling an end user to build
`ai-dememory:local` would silently switch them from the published 2.1.0 package
to unpublished source. Docker is therefore not an installation or MCP setup
route in this interim state.

Use the installed 2.1.0 CLI and the generated `mcp-config` fragment above. Once
the stable 2.1.1 package and its exact release evidence have been read back,
this guide can publish a verified Docker recipe. That future mode remains local
stdio only and must not expose a network port without a separate authentication,
authorization, and privacy design.

## Maintainer-only Checkout Diagnostics

The following source-checkout commands are only for a contributor or CI/release
maintainer verifying a trusted checkout. They do not create an installable
Docker route, cannot replace the published package, and must never be copied
into a client setup or pointed at the public repository as a vault:

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
