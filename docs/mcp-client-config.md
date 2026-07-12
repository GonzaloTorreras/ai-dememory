# MCP Client Configuration

The server is local-first and uses stdio. Configure clients to run the command
from this repository checkout.

## Preferred Command

Generate config from inside a memory vault:

```bash
ai-dememory mcp-config --client codex
```

For Codex, the default is `--profile core`. Use `--profile working` for session
writes, `--profile review` for inbox/review workflows, or the explicit
`--profile admin` escape hatch for the unfiltered 74-tool server. Generic and
Claude config output defaults to `admin` because those formats do not enforce
Codex `enabled_tools`; requesting a narrower profile is rejected instead of
silently claiming a budget that the client cannot enforce. Profile
definitions and current schema measurements are documented in
[MCP tool profiles](mcp-tool-profiles.md).

For Codex, the command emits native TOML for `~/.codex/config.toml` (or a
trusted project's `.codex/config.toml`) and sets `AI_DEMEMORY_ROOT` to the
vault path:

```toml
[mcp_servers.ai-dememory]
command = "ai-dememory"
args = ["mcp", "--stdio"]
enabled_tools = ["memory.search", "memory.get", "memory.context", "memory.graph", "memory.doctor", "memory.working_current", "memory.working_status"]

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
  "args": ["mcp", "--stdio"],
  "env": {
    "AI_DEMEMORY_ROOT": "D:\\Github\\ai-dememory"
  }
}
```

Without editable install:

```json
{
  "command": "py",
  "args": ["-3", "scripts\\ai_dememory.py", "mcp", "--stdio"],
  "cwd": "D:\\Github\\ai-dememory",
  "env": {
    "AI_DEMEMORY_ROOT": "D:\\Github\\ai-dememory"
  }
}
```

The equivalent local checkout smoke command is:

```powershell
py -3 scripts\ai_dememory.py --root D:\Github\ai-dememory mcp-client-smoke --command py --command-arg -3 --command-arg scripts\ai_dememory.py
```

For WSL/Linux paths:

```json
{
  "command": "python3",
  "args": ["scripts/ai_dememory.py", "mcp", "--stdio"],
  "cwd": "/home/user/code/ai-dememory",
  "env": {
    "AI_DEMEMORY_ROOT": "/home/user/code/ai-dememory"
  }
}
```

WSL/Linux checkout smoke:

```bash
python3 scripts/ai_dememory.py --root /home/user/code/ai-dememory mcp-client-smoke \
  --command python3 \
  --command-arg scripts/ai_dememory.py
```

Adapt field names to the host application's MCP configuration format. The
important contract is command, args, working directory, and `AI_DEMEMORY_ROOT`.
`ai-dememory mcp-client-smoke --config <file>` honors a `cwd` field when a
client config includes one. Pass `--command` and repeated `--command-arg`
values to smoke an existing config file with an explicit launch command while
preserving the config's environment and tool allowlist. When the config includes
`enabled_tools`, the smoke also calls `tools/list` and fails if any enabled tool
is absent from the launched server, following `nextCursor` until the final page.

For the repo plugin config:

```bash
python3 scripts/ai_dememory.py mcp-client-smoke \
  --config plugins/ai-dememory/.mcp.json \
  --command python3 \
  --command-arg scripts/ai_dememory.py
```

## Preflight

Before connecting a client:

```bash
python3 scripts/ai_dememory.py doctor
python3 scripts/ai_dememory.py verify-mcp
python3 scripts/ai_dememory.py index
python3 scripts/ai_dememory.py mcp-client-smoke --command python3 --command-arg scripts/ai_dememory.py
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

The Codex plugin config uses the same seven-tool `core` allowlist as generated
Codex TOML. Direct clients can opt into `working` or `review`; `admin` removes
the allowlist and therefore exposes the complete server. Broad execution tools
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
