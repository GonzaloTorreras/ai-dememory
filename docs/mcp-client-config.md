# MCP Client Configuration

This page explains the fragment that an AI client launches. For the ordinary
user flow, follow [Local MCP server setup](local-mcp.md): install the CLI,
create a separate private vault, generate a fragment, and copy it into the
client yourself. A source checkout may be a development working directory, but
it must never be the vault.

Published stable 2.1.0 is the current PyPI release. TestPyPI prerelease 2.1.1rc1
is an evaluation route only. The stable generated configuration keeps its
historical runtime pin; the prerelease removes that emitted pin.

## Generate, Do Not Hand Assemble

For stable 2.1.0, create the vault with its required legacy compatibility
argument and generate a fragment only for the client you use:

```bash
ai-dememory init ~/code/my-memory --wizard --require-version 2.1.0
ai-dememory --root ~/code/my-memory mcp-config --client codex
```

For TestPyPI 2.1.1rc1, the first command becomes
`ai-dememory init ~/code/my-memory --wizard` after its exact evaluation install
from [Installation](install.md). Do not substitute that prerelease route for
the published PyPI installation.

`mcp-config` prints configuration; it does not edit a host. Regenerate and
inspect it when you upgrade an existing stable install:

```bash
pipx install --force ai-dememory==2.1.0
ai-dememory --root ~/code/my-memory mcp-config --client codex
```

`ai-dememory version-check 2.1.0` is a CI/support diagnostic, not a routine
installation or setup command.

## What To Copy

For Codex, copy the generated TOML into `~/.codex/config.toml` or a trusted
project's `.codex/config.toml`. The following is the stable 2.1.0 shape; do not
copy the legacy `--require-version` value into a prerelease-generated fragment:

```toml
[mcp_servers.ai-dememory]
command = "ai-dememory"
args = ["mcp", "--stdio", "--idle-timeout-seconds", "600", "--require-version", "2.1.0", "--profile", "core", "--require-bound-root"]
enabled_tools = ["memory.search", "memory.get", "memory.context", "memory.doctor"]

[mcp_servers.ai-dememory.env]
AI_DEMEMORY_ROOT = "D:\\memory-vault"
```

Claude and generic clients use their own JSON configuration shape. The essential
contract is the installed `ai-dememory` command, `mcp --stdio`, an explicit
`AI_DEMEMORY_ROOT`, a server profile, and `--require-bound-root`. An unbound
configuration must fail instead of falling back to an unintended vault or this
public source checkout.

```json
{
  "command": "ai-dememory",
  "args": ["mcp", "--stdio", "--idle-timeout-seconds", "600", "--profile", "core", "--require-bound-root"],
  "env": {
    "AI_DEMEMORY_ROOT": "D:\\memory-vault"
  }
}
```

## Profiles And Process Lifecycle

Every generated client defaults to the server-enforced `core` profile. Select
`working` for session writes, `review` for inbox/review work, or `admin` only
for deliberate broad maintenance. `admin` is a compatibility escape hatch, not
the recommended default. Codex receives a matching client allowlist, while the
server enforces the profile for every client. See
[MCP tool profiles](mcp-tool-profiles.md) for the current capability matrix.

Generated configs also carry an idle lease: 600 seconds for `balanced`, and
120/600/1800 seconds for wizard `minimal`/`balanced`/`active`. This bounds an
abandoned MCP process when a host keeps stdio open after an agent ends. Use
`--idle-timeout-seconds 0` only under an external lifecycle supervisor.

## Optional User Diagnostics

Before connecting a client, these installed-CLI checks are sufficient for a
private vault:

```bash
ai-dememory --root ~/code/my-memory doctor
ai-dememory --root ~/code/my-memory index
```

After copying the generated fragment, this advanced diagnostic launches the
bound installed CLI and verifies `initialize` and `ping`:

```bash
ai-dememory --root ~/code/my-memory dev mcp-client-smoke
```

It is optional—not a first-run requirement. It matches JSON-RPC responses by
id and, when an `enabled_tools` list is present, verifies paginated
`tools/list` coverage.

## Maintainer-Only Checkout And PR Checks

The source-checkout forms below are for development, CI, or support debugging.
They intentionally exercise code in a checkout and are not user configuration
recipes. Keep the actual vault separate.

```powershell
py -3 scripts\ai_dememory.py --root D:\memory-vault mcp-client-smoke --command py --command-arg -3 --command-arg scripts\ai_dememory.py
```

```bash
python3 scripts/ai_dememory.py --root /home/user/memory-vault mcp-client-smoke \
  --command python3 \
  --command-arg scripts/ai_dememory.py
```

The repository plugin smoke is also maintainer-only because it uses checked-in
public fixtures, not a private vault:

```bash
python3 scripts/ai_dememory.py mcp-client-smoke \
  --config plugins/ai-dememory/.mcp.json \
  --command python3 \
  --command-arg scripts/ai_dememory.py
```

After a draft PR exists, run the runtime smoke from that checkout—not from a
user vault:

```bash
AI_DEMEMORY_PR_URL="https://github.com/GonzaloTorreras/ai-dememory/pull/<number>" python3 scripts/ai_dememory.py mcp-smoke
```

The runtime smoke initializes protocol `2025-11-25`, sends
`notifications/initialized`, verifies `ping`, checks paginated capabilities and
safe resources, rejects sensitive resources by default, and confirms proposal
writes remain in `inbox/llm-captures/`.

## Security Boundaries

- Do not configure the server against an untrusted checkout.
- Do not turn stdio MCP into a network service without a separate
  authentication and authorization design.
- Keep `include_sensitive` disabled unless a local user explicitly requests it.
- `memory.write_proposal` writes review candidates only; it never promotes
  durable memory.
- The checked-in public Codex plugin uses a three-tool `public` ceiling.
  Generated private-vault configuration uses four-tool `core`; broad tools such
  as reindex, secret scan, provider import, and maintenance remain admin-only.
