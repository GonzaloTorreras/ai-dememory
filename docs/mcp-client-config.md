# MCP Client Configuration

The server is local-first and uses stdio. Configure clients to run the
installed command against an explicit private vault. A source checkout may be
the command working directory for development only; it must not also be the
vault.

**Release scope:** Published stable 2.1.0 is the only package available from
PyPI. Source candidate 2.1.1rc1 is unreleased and not installable from a package
index until it is tagged and published. The stable generated configuration below
retains its historical runtime pin; the candidate removes that emitted pin.

The 2.1.0 release line includes the server-enforced profiles, required-root flag,
enabled-tool allowlist, and generated idle leases shown below. See
[Local MCP server setup](local-mcp.md) for the complete installed-tool flow.

## Preferred Command

Create the vault with the wizard, then generate config only for a client you
intend to connect:

```bash
ai-dememory init ~/code/my-memory --wizard --require-version 2.1.0
ai-dememory --root ~/code/my-memory mcp-config --client codex
```

The source candidate makes only the first line simpler:
`ai-dememory init ~/code/my-memory --wizard`. It is an unreleased behavior,
not a package installation instruction.

After upgrading, run the generator again from every private vault, inspect its
output, replace the previous host entry, and verify the installed launch path:

```bash
pipx install --force ai-dememory==2.1.0
ai-dememory --root ~/code/my-memory mcp-config --client codex
ai-dememory --root ~/code/my-memory mcp-client-smoke
```

The generator prints configuration; it does not silently edit the host.
`ai-dememory version-check 2.1.0` remains available for CI or support
diagnostics, not routine setup.

Every client defaults to the server-enforced `--profile core`. Use
`--profile working` for session writes, `--profile review` for inbox/review
workflows, or the explicit `--profile admin` escape hatch for the complete
historical server surface. `admin` is retained for compatibility and broad
maintenance, not as the recommended default. Codex also receives a matching
`enabled_tools` allowlist, but
generic and Claude clients are bounded even without that client feature because
the launched server enforces the profile. Profile definitions and current
schema measurements are documented in
[MCP tool profiles](mcp-tool-profiles.md).

Generated configs also enforce an idle process lease. `balanced` defaults to
600 seconds, while onboarding emits 120/600/1800 seconds for
`minimal`/`balanced`/`active`. This bounds abandoned MCP processes when a host
keeps stdio open after an agent ends. Set `--idle-timeout-seconds 0` only for a
deliberately persistent server with external lifecycle supervision.

For Codex, the command emits native TOML for `~/.codex/config.toml` (or a
trusted project's `.codex/config.toml`) and sets `AI_DEMEMORY_ROOT` to the
vault path:

```toml
[mcp_servers.ai-dememory]
command = "ai-dememory"
args = ["mcp", "--stdio", "--idle-timeout-seconds", "600", "--require-version", "2.1.0", "--profile", "core", "--require-bound-root"]
enabled_tools = ["memory.search", "memory.get", "memory.context", "memory.doctor"]

[mcp_servers.ai-dememory.env]
AI_DEMEMORY_ROOT = "D:\\memory-vault"
```

Claude and generic clients continue to receive JSON in their native shape.

Smoke test the generated installed-CLI config:

```bash
ai-dememory mcp-client-smoke
```

For a Docker-backed local stdio server:

```bash
docker build -t ai-dememory:local .
ai-dememory mcp-config --client codex --mode docker --root /path/to/vault
```

Generic JSON form from an editable install:

```json
{
  "command": "ai-dememory",
  "args": ["mcp", "--stdio", "--idle-timeout-seconds", "600", "--profile", "core", "--require-bound-root"],
  "env": {
    "AI_DEMEMORY_ROOT": "D:\\memory-vault"
  }
}
```

Without editable install:

```json
{
  "command": "py",
  "args": ["-3", "scripts\\ai_dememory.py", "mcp", "--stdio", "--idle-timeout-seconds", "600", "--profile", "core", "--require-bound-root"],
  "cwd": "D:\\Github\\ai-dememory",
  "env": {
    "AI_DEMEMORY_ROOT": "D:\\memory-vault"
  }
}
```

The equivalent local checkout smoke command is:

```powershell
py -3 scripts\ai_dememory.py --root D:\memory-vault mcp-client-smoke --command py --command-arg -3 --command-arg scripts\ai_dememory.py
```

For WSL/Linux paths:

```json
{
  "command": "python3",
  "args": ["scripts/ai_dememory.py", "mcp", "--stdio", "--idle-timeout-seconds", "600", "--profile", "core", "--require-bound-root"],
  "cwd": "/home/user/code/ai-dememory",
  "env": {
    "AI_DEMEMORY_ROOT": "/home/user/memory-vault"
  }
}
```

WSL/Linux checkout smoke:

```bash
python3 scripts/ai_dememory.py --root /home/user/memory-vault mcp-client-smoke \
  --command python3 \
  --command-arg scripts/ai_dememory.py
```

Adapt field names to the host application's MCP configuration format. The
important contract is command, args, working directory, `AI_DEMEMORY_ROOT`, the
server profile, and `--require-bound-root`. An unbound generated configuration
must fail closed instead of falling back to the public source checkout or an
unintended vault.
`ai-dememory mcp-client-smoke --config <file>` honors a `cwd` field when a
client config includes one. Pass `--command` and repeated `--command-arg`
values to smoke an existing config file with an explicit launch command while
preserving the config's environment and tool allowlist. When the config includes
`enabled_tools`, the smoke also calls `tools/list` and fails if any enabled tool
is absent from the launched server, following `nextCursor` until the final page.

For the repository plugin's source-development smoke only:

```bash
python3 scripts/ai_dememory.py mcp-client-smoke \
  --config plugins/ai-dememory/.mcp.json \
  --command python3 \
  --command-arg scripts/ai_dememory.py
```

That command intentionally exercises the repository's public demo fixtures. It
is not a user MCP configuration and must not be repurposed as a private vault.

## Preflight

Before connecting a client:

```bash
ai-dememory --root /path/to/private-memory-vault doctor
ai-dememory --root /path/to/private-memory-vault verify-mcp
ai-dememory --root /path/to/private-memory-vault index
ai-dememory --root /path/to/private-memory-vault mcp-client-smoke
```

After a draft PR exists, run the runtime smoke from the same checkout:

```bash
AI_DEMEMORY_PR_URL="https://github.com/GonzaloTorreras/ai-dememory/pull/<number>" python3 scripts/ai_dememory.py mcp-smoke
```

PowerShell:

```powershell
$env:AI_DEMEMORY_PR_URL = "https://github.com/GonzaloTorreras/ai-dememory/pull/<number>"
py -3 scripts\ai_dememory.py mcp-smoke
```

The smoke initializes protocol `2025-11-25`, sends
`notifications/initialized`, verifies `ping`, lists tools, resources, and
prompts, reads a safe resource, checks sensitive-resource rejection, verifies
proposal writes stay in `inbox/llm-captures/`, and checks MCP path boundaries.
Client-config smoke matches JSON-RPC responses by id and skips response-less
server notifications.

## Exposed Capabilities

- Tools: `memory.search`, `memory.get`, `memory.write_proposal`,
  `memory.mark_seen`, `memory.reindex`, `memory.consolidate`,
  `memory.secret_scan`, `memory.graph`, `memory.context`,
  `memory.capture_miss`, `memory.recall_miss_candidate`, `memory.recall_fixture_status`,
  `memory.recall_review_plan`, `memory.recall_review_packet`,
  `memory.recall_review_packet_archive_status`,
  `memory.recall_review_packet_archive_retention_plan`,
  `memory.recall_miss_review`,
  `memory.vector_status`, `memory.outcome`,
  `memory.lifecycle_scores`,
  `memory.maintenance_status`, `memory.import_chats`, `memory.maintenance_run`,
  `memory.schedule_plan`, `memory.schedule_status`,
  `memory.sleep_plan`, `memory.sleep_apply_reviewed`,
  `memory.working_current`, `memory.working_status`,
  `memory.working_snapshot`, `memory.working_handoff`,
  `memory.providers_detect`, `memory.providers_status`,
  `memory.providers_plan`, `memory.setup_plan`, `memory.setup_health`,
  `memory.hook_status`, `memory.hook_capture_review`,
  `memory.review_false_positives`,
  `memory.review_stale_false_positives`,
  `memory.false_positive_ignore`, `memory.false_positive_unignore`,
  `memory.review_conflicts`,
  `memory.conflict_dismiss`, `memory.conflict_keep`,
  `memory.conflict_merge_proposal`,
  `memory.review_modes`, `memory.review_configure_mode`,
  `memory.review_plan`, `memory.review_recommendation`,
  `memory.review_recommendations`,
  `memory.review_recommendation_archive_status`,
  `memory.review_recommendation_archive_restore_preview`,
  `memory.review_recommendation_outcome_report`,
  `memory.review_recommendation_outcome`,
  `memory.acceptance_status`,
  `memory.acceptance_verify`, `memory.acceptance_plan`,
  `memory.acceptance_template`, `memory.acceptance_packet`,
  `memory.acceptance_packet_archive_status`,
  `memory.acceptance_packet_archive_retention_plan`,
  `memory.release_evidence`, and `memory.release_evidence_report`.
- Resources: `memory://id/{id}` and `memory://path/{path}` for public/internal
  canonical memories.
- Prompts: `memory_recall_context`, `memory_capture_proposal`,
  `memory_review_inbox`.
- Utilities: `initialize`, `notifications/initialized`, and `ping`.

The checked-in public Codex plugin uses a three-tool `public` allowlist and
server ceiling; generated private-vault Codex TOML defaults to four-tool
`core`. Direct clients can opt into `working` or `review`; `admin` removes the
allowlist and therefore exposes the complete server. Broad execution tools
such as `memory.reindex`, `memory.secret_scan`, `memory.import_chats`, and
`memory.maintenance_run` remain admin-only.

## Security Notes

- Do not configure this server against an untrusted checkout.
- Do not expose the stdio server as a network service without a separate
  authentication and authorization design.
- Keep `include_sensitive` disabled unless the user explicitly asks to retrieve
  private/sensitive memory.
- `memory.write_proposal` writes only to `inbox/llm-captures/`; it does not
  promote durable memories.
- Review write tools only update `.ai-dememory-ignore.toml` or write merge
  proposals under `inbox/conflict-resolution/`.
