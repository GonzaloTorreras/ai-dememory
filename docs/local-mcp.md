# Local MCP Server Setup

`ai-dememory` is local-first. The MCP server uses stdio and reads a private
memory vault through `AI_DEMEMORY_ROOT`.

## Exact 2.1.0 Installed CLI

Install the tool, create a vault, then generate client config:

```bash
pipx install ai-dememory==2.1.0
ai-dememory version-check 2.1.0
ai-dememory init ~/code/my-memory
cd ~/code/my-memory
ai-dememory doctor
ai-dememory index
ai-dememory mcp-config --client codex --require-version 2.1.0
```

Verify that the generated installed-CLI config launches and responds over
stdio:

```bash
ai-dememory mcp-client-smoke
```

PowerShell:

```powershell
pipx install ai-dememory==2.1.0
ai-dememory version-check 2.1.0
ai-dememory init D:\Github\my-memory
Set-Location D:\Github\my-memory
ai-dememory mcp-config --client codex --require-version 2.1.0
```

The verified 2.1.0 executable generates the following hardened Codex TOML shape:

```toml
[mcp_servers.ai-dememory]
command = "ai-dememory"
args = ["mcp", "--stdio", "--idle-timeout-seconds", "600", "--require-version", "2.1.0", "--profile", "core", "--require-bound-root"]
enabled_tools = ["memory.search", "memory.get", "memory.context", "memory.doctor"]

[mcp_servers.ai-dememory.env]
AI_DEMEMORY_ROOT = "<vault path>"
```

After upgrading an existing PyPI installation, regenerate the client fragment
from each private vault and smoke-test the installed command:

```bash
pipx install --force ai-dememory==2.1.0
ai-dememory version-check 2.1.0
cd ~/code/my-memory
ai-dememory mcp-config --client codex --require-version 2.1.0
ai-dememory mcp-client-smoke
```

Inspect and replace the prior host entry yourself; `mcp-config` prints the
configuration and does not silently edit Codex, Claude, or another client. Its
`--require-version 2.1.0` check runs inside the generator before any output and
is embedded again in the emitted server command. If a host package or Docker
image originated from a release candidate or mutable Git checkout,
replace it with `pipx uninstall ai-dememory` followed by
`pipx install ai-dememory==2.1.0` and `ai-dememory version-check 2.1.0`
before regenerating the fragment.

This is the shape accepted by Codex in `~/.codex/config.toml` or a trusted
project's `.codex/config.toml`. Claude and generic output modes use JSON.
Generated Codex, Claude, and generic configs use the server-enforced four-tool
`core` profile by default and require an explicitly bound vault. Pass
`--profile working`, `--profile review`, or explicitly `--profile admin` to
change the advertised and callable surface. Codex receives the same allowlist
client-side as defense in depth. `admin` preserves the complete historical MCP
surface for compatibility and broad maintenance; it is an explicit escape
hatch, not the recommended default.

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
python3 scripts/ai_dememory.py --root /path/to/vault mcp-config --client codex --require-version 2.1.0 \
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
ai-dememory mcp-config --client codex --mode docker --root ~/code/my-memory --require-version 2.1.0
ai-dememory mcp-client-smoke --mode docker --image ai-dememory:local --root ~/code/my-memory
```

Generated Docker config appends
`mcp --stdio --idle-timeout-seconds 600 --require-version 2.1.0 --profile core --require-bound-root`
after the image name and
binds the selected vault at `/memory`; clients only need stdin/stdout attached.

Use the `mcp-client-smoke` command above for the end-to-end test. Stable guides
intentionally do not provide raw `docker run` recipes: generated configuration
owns the exact mount, image, version, profile, root binding and resource lease.
The selected root must be the separately initialized private vault, not the
public source checkout.

Do not expose this container as a network service without a separate
authentication, authorization, and privacy design.

## Related Local Transports

Use the MCP stdio server for LLM clients when possible. For local scripts or
dashboards that need HTTP, use the separate loopback REST API documented in
`docs/local-api.md`.
