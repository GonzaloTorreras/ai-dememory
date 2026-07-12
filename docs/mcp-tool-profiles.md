# MCP Tool Profiles

The MCP server retains all 74 tools for compatibility, embedding, and advanced
administration. Clients should not advertise that entire surface to a model by
default. `ai-dememory mcp-config --client codex` and the bundled Codex plugin
therefore use `core`.

Profiles are additive:

| Profile | Tools | Schema bytes | Est. tokens | Intended use |
| --- | ---: | ---: | ---: | --- |
| `core` | 7 | 5,084 | 1,271 | Recall, bounded context, relationship lookup, basic health, and current task state. |
| `working` | 12 | 8,871 | 2,218 | `core` plus snapshots, handoffs, retrieval telemetry, misses, and usefulness feedback. |
| `review` | 44 | 48,691 | 12,173 | `working` plus review-first proposals, recall-miss, provenance, hook-capture, import, conflict, and recommendation review. |
| `admin` | 74 | 77,483 | 19,371 | Explicit unfiltered server surface, including maintenance, imports, indexing, release, and acceptance tooling. |

These measurements come from the 2.1.0 server definitions and are guarded by
the reproducible inventory command below; rerun it whenever a schema changes.

`admin` intentionally omits `enabled_tools` from generated Codex TOML. This is
the backwards-compatible escape hatch and must be selected explicitly.

Generate configuration:

```bash
ai-dememory mcp-config --client codex                  # core
ai-dememory mcp-config --client codex --profile working
ai-dememory mcp-config --client codex --profile review
ai-dememory mcp-config --client codex --profile admin
```

Inspect the exact allowlist and measure serialized tool-definition cost from
the current server source:

```bash
ai-dememory dev mcp-inventory --profile core --json
ai-dememory dev mcp-inventory --profile working --json
ai-dememory dev mcp-inventory --profile review --json
ai-dememory dev mcp-inventory --profile admin --json
```

The reported `schema_bytes` is compact UTF-8 JSON for the selected MCP tool
definitions. `estimated_schema_tokens` is a transparent bytes/4 estimate, not
a tokenizer-specific promise. Inventory and release guards fail if a named
profile references a tool the server no longer exposes or if the plugin
allowlist drifts from `core`.

The profile definitions live in `ai_dememory_tool/mcp_profiles.py`. The server
does not enforce them: a client without allowlist support can still see all 74
tools. Generated generic and Claude configs therefore default to `admin` and
reject narrower profiles; use Codex or another client-specific allowlist when
prompt cost matters.
