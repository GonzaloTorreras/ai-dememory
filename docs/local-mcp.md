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

Before PyPI publication, install from GitHub:

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
args = ["mcp", "--stdio"]

[mcp_servers.ai-dememory.env]
AI_DEMEMORY_ROOT = "<vault path>"
```

This is the shape accepted by Codex in `~/.codex/config.toml` or a trusted
project's `.codex/config.toml`. Claude and generic output modes use JSON.

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

The image default command is `ai-dememory mcp --stdio`, so MCP clients only
need to launch the container with stdin/stdout attached.

Smoke test manually:

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"ping"}' \
  | docker run --rm -i -e AI_DEMEMORY_ROOT=/memory -v "$PWD:/memory" ai-dememory:local
```

Do not expose this container as a network service without a separate
authentication, authorization, and privacy design.

## Related Local Transports

Use the MCP stdio server for LLM clients when possible. For local scripts or
dashboards that need HTTP, use the separate loopback REST API documented in
`docs/local-api.md`.
