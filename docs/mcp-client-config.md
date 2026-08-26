# MCP Client Configuration

This page explains the fragment that an AI client launches. For the ordinary
user flow, follow [Local MCP server setup](local-mcp.md): install the CLI,
create a separate private vault, generate a fragment, and copy it into the
client yourself. A source checkout may be a development working directory, but
it must never be the vault.

Use the stable PyPI package for this configuration. The source checkout is not
a user-runtime fallback.

## Generate, Do Not Hand Assemble

Create the vault and generate a fragment only for the client you use:

```bash
ai-dememory init ~/code/my-memory --wizard
ai-dememory --root ~/code/my-memory mcp-config --client codex
```

`mcp-config` prints configuration; it does not edit a host. Regenerate and
inspect it when you upgrade an existing stable install:

```bash
pipx install --force ai-dememory
ai-dememory --root ~/code/my-memory mcp-config --client codex
```

`ai-dememory --version` is available for a PATH or package diagnostic; it is
not a routine setup command.

## What To Copy

For Codex, copy the generated TOML into `~/.codex/config.toml` or a trusted
project's `.codex/config.toml`. A representative generated fragment is:

```toml
[mcp_servers.ai-dememory]
command = "ai-dememory"
args = ["mcp", "--stdio", "--idle-timeout-seconds", "600", "--profile", "core", "--require-bound-root"]
enabled_tools = ["memory.search", "memory.get", "memory.context", "memory.doctor"]

[mcp_servers.ai-dememory.env]
AI_DEMEMORY_ROOT = "D:\\memory-vault"
```

Generate and inspect a vault-specific fragment with `mcp-config`; do not
hand-assemble its runtime argument list.

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
recipes. Keep the initialized smoke vault separate, and use an absolute path to
the source script because the launched child runs from that vault.

```powershell
py -3 scripts/ai_dememory.py init D:/Temp/ai-dememory-mcp-smoke --no-wizard
py -3 scripts/ai_dememory.py --root D:/Temp/ai-dememory-mcp-smoke mcp-client-smoke --command py --command-arg=-3 --command-arg D:/code/ai-dememory/scripts/ai_dememory.py
```

```bash
python3 scripts/ai_dememory.py init /tmp/ai-dememory-mcp-smoke --no-wizard
python3 scripts/ai_dememory.py --root /tmp/ai-dememory-mcp-smoke mcp-client-smoke \
  --command python3 \
  --command-arg /home/user/code/ai-dememory/scripts/ai_dememory.py
```

The repository plugin smoke is also maintainer-only. It reads the checked-in
public client config, while the launched server remains bound to the separate
initialized smoke vault; no private path is written into the config:

```bash
python3 scripts/ai_dememory.py --root /tmp/ai-dememory-mcp-smoke mcp-client-smoke \
  --config /home/user/code/ai-dememory/plugins/ai-dememory/.mcp.json \
  --command python3 \
  --command-arg /home/user/code/ai-dememory/scripts/ai_dememory.py
```

Replace the example absolute checkout path if needed, then delete the
disposable vault after these diagnostics. Never add a vault marker to the
public checkout.

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
