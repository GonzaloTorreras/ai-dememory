# Local MCP Server Setup

`ai-dememory` is local-first. The MCP server uses stdio and reads a private
memory vault through `AI_DEMEMORY_ROOT`.

## Installed CLI

Install the tool, create a vault, then generate client config:

```bash
pipx install ai-dememory
ai-dememory init ~/code/my-memory
cd ~/code/my-memory
ai-dememory doctor
ai-dememory index
ai-dememory mcp-config --client codex
```

Verify that the generated installed-CLI config launches and responds over
stdio:

```bash
ai-dememory mcp-client-smoke
```

To test the current unreleased source branch instead of stable PyPI 2.0.0,
install from GitHub:

```bash
pipx install git+https://github.com/GonzaloTorreras/ai-dememory.git
```

PowerShell:

```powershell
pipx install ai-dememory
ai-dememory init D:\Github\my-memory
Set-Location D:\Github\my-memory
ai-dememory mcp-config --client codex
```

The generated Codex config uses TOML:

```toml
[mcp_servers.ai-dememory]
command = "ai-dememory"
args = ["mcp", "--stdio", "--idle-timeout-seconds", "600", "--profile", "core", "--require-bound-root"]
enabled_tools = ["memory.search", "memory.get", "memory.context", "memory.doctor"]

[mcp_servers.ai-dememory.env]
AI_DEMEMORY_ROOT = "<vault path>"
```

This is the shape accepted by Codex in `~/.codex/config.toml` or a trusted
project's `.codex/config.toml`. Claude and generic output modes use JSON.
Generated Codex, Claude, and generic configs use the server-enforced four-tool
`core` profile by default and require an explicitly bound vault. Pass
`--profile working`, `--profile review`, or explicitly `--profile admin` to
change the advertised and callable surface. Codex receives the same allowlist
client-side as defense in depth.

Generated servers also carry a bounded idle lease so a client or completed
agent cannot leave an unused Python MCP process alive forever. The default
`balanced` lease is 600 seconds; onboarding uses 120/600/1800 seconds for
`minimal`/`balanced`/`active`. A client may reconnect on its next call. Use
`--idle-timeout-seconds 0` only when another supervisor owns process cleanup.

The server's protocol reader has its own response/idle deadline and closes
cleanly on stdin EOF. Package-owned Git and maintenance children never inherit
MCP protocol stdin: they run non-interactively in an owned process group/tree,
and timeout/shutdown reaps descendants before the MCP process exits. Windows
uses a kill-on-close Job Object; POSIX uses an owned session/process group.
These guarantees cover ai-dememory-owned children; the host application
remains responsible for its unrelated browser, Node, Python, or plugin tool
servers.

From a source checkout without an editable install, generate and smoke test a
checkout-safe command:

```bash
python3 scripts/ai_dememory.py --root /path/to/vault mcp-config --client codex \
  --command python3 \
  --command-arg /path/to/ai-dememory/scripts/ai_dememory.py
python3 scripts/ai_dememory.py --root /path/to/vault mcp-client-smoke \
  --command python3 \
  --command-arg /path/to/ai-dememory/scripts/ai_dememory.py
```

## Docker

Docker is supported only for local stdio MCP usage. It does not expose ports or
run a remote server.

Build the image:

```bash
docker build -t ai-dememory:local .
```

Create or reuse a vault, then generate Docker client config:

```bash
ai-dememory mcp-config --client codex --mode docker --root ~/code/my-memory
ai-dememory mcp-client-smoke --mode docker --image ai-dememory:local --root ~/code/my-memory
```

The generated Docker config runs:

```bash
docker run --rm -i -e AI_DEMEMORY_ROOT=/memory -v <vault path>:/memory ai-dememory:local
```

Generated Docker config appends
`mcp --stdio --idle-timeout-seconds 600 --profile core --require-bound-root`
after the image name and
binds the selected vault at `/memory`; clients only need stdin/stdout attached.

Smoke test manually:

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"ping"}' \
  | docker run --rm -i -e AI_DEMEMORY_ROOT=/memory -v "<vault path>:/memory" ai-dememory:local
```

Replace `<vault path>` with the separately initialized private vault, not the
public source checkout.

Do not expose this container as a network service without a separate
authentication, authorization, and privacy design.

## Related Local Transports

Use the MCP stdio server for LLM clients when possible. For local scripts or
dashboards that need HTTP, use the separate loopback REST API documented in
`docs/local-api.md`.
