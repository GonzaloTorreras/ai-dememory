# Local MCP Server Setup

Use MCP when an AI client such as Codex or Claude needs local memory tools.
The server uses stdio, not a network port, and its configuration binds the
installed `ai-dememory` command to one private vault through
`AI_DEMEMORY_ROOT`.

This is an optional integration after installation. The public source repository
contains demo/validation fixtures only; it is never the vault to connect.

## User Path: Install, Create A Vault, Then Connect A Client

Install the stable PyPI package, then create a separately bound private vault.

```bash
pipx install ai-dememory
ai-dememory init ~/code/my-memory --wizard
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
plugin processes owned by the host application. They apply after the runtime
has completed process-tree ownership; an uncatchable parent death or host power
loss still requires an external supervisor.

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
pipx install --force ai-dememory
ai-dememory --root ~/code/my-memory mcp-config --client codex
```

Regenerate the fragment from the installed stable package rather than treating a
source checkout as a fallback. Version diagnostics are for CI or support work,
not setup.

## Docker Diagnostics Are Maintainer-only

The Dockerfile supports isolated CI and checkout diagnostics. It is not an
installation or MCP setup route: building `ai-dememory:local` runs source
code and must not replace the installed CLI.

Use the installed CLI and the generated `mcp-config` fragment above. Any future
Docker user route remains local stdio only and must not expose a network port
without a separate authentication, authorization, and privacy design.

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
