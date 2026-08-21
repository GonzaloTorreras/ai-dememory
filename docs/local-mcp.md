# Local MCP Server Setup

`ai-dememory` is local-first. The MCP server uses stdio and reads a private
memory vault through `AI_DEMEMORY_ROOT`.

## Install And Create A Vault

Install the tool and let the wizard create the vault and choose its bounded
operating policy:

```bash
pipx install ai-dememory==2.1.0
ai-dememory init ~/code/my-memory --wizard
```

Connecting a client is separate and optional. Generate the fragment for the
specific private vault, inspect it, then copy it into the client configuration:

```bash
ai-dememory --root ~/code/my-memory mcp-config --client codex
```

PowerShell:

```powershell
pipx install ai-dememory==2.1.0
ai-dememory init D:\Github\my-memory --wizard
ai-dememory --root D:\Github\my-memory mcp-config --client codex
```

The generated Codex fragment carries the selected profile, root binding, and
idle lease:

```toml
[mcp_servers.ai-dememory]
command = "ai-dememory"
args = ["mcp", "--stdio", "--idle-timeout-seconds", "600", "--profile", "core", "--require-bound-root"]
enabled_tools = ["memory.search", "memory.get", "memory.context", "memory.doctor"]

[mcp_servers.ai-dememory.env]
AI_DEMEMORY_ROOT = "<vault path>"
```

After upgrading an existing PyPI installation, regenerate the client fragment
from each private vault and, when needed, smoke-test the installed command:

```bash
pipx install --force ai-dememory==2.1.0
ai-dememory --root ~/code/my-memory mcp-config --client codex
ai-dememory --root ~/code/my-memory mcp-client-smoke
```

Inspect and replace the prior host entry yourself; `mcp-config` prints the
configuration and does not silently edit Codex, Claude, or another client. If a
host package or Docker image originated from a release candidate or mutable Git
checkout, replace it with `pipx uninstall ai-dememory` followed by
`pipx install ai-dememory==2.1.0` before regenerating the fragment.

`ai-dememory version-check 2.1.0` remains an explicit CI or support diagnostic;
it is not a required installation or configuration step.

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

Generated Docker config appends
`mcp --stdio --idle-timeout-seconds 600 --profile core --require-bound-root`
after the image name and
binds the selected vault at `/memory`; clients only need stdin/stdout attached.

Use the `mcp-client-smoke` command above for the end-to-end test. Stable guides
intentionally do not provide raw `docker run` recipes: generated configuration
owns the exact mount, image selection, profile, root binding and resource lease.
The selected root must be the separately initialized private vault, not the
public source checkout.

Do not expose this container as a network service without a separate
authentication, authorization, and privacy design.

## Related Local Transports

Use the MCP stdio server for LLM clients when possible. For local scripts or
dashboards that need HTTP, use the separate loopback REST API documented in
`docs/local-api.md`.
