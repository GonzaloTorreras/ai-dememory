# Memory Graph

`ai-dememory graph` builds a lightweight relationship graph from canonical
Markdown memory files.

The graph is generated, not canonical. Markdown remains the source of truth.
When `indexes/memory.sqlite` exists, graph generation reads the SQLite index for
faster responses. If the index is missing, it falls back to parsing Markdown.

## What It Contains

Nodes:

- `memory`: one node per public/internal memory by default.
- `tag`: one node per tag.
- `project`: one node per project value.
- `type`: one node per memory type.
- `scope`: one node per scope.

Edges:

- `tagged`: memory to tag.
- `belongs_to_project`: memory to project.
- `has_type`: memory to type.
- `has_scope`: memory to scope.
- `references`: memory to another memory when the body mentions another
  canonical `mem_*` id.

Private and sensitive memories are excluded unless the caller explicitly passes
`--include-sensitive` or `include_sensitive=true`.

## CLI

```bash
ai-dememory index
ai-dememory graph
ai-dememory graph --json
```

## MCP

The MCP server exposes the graph through the read-only `memory.graph` tool:

```json
{
  "name": "memory.graph",
  "arguments": {
    "include_sensitive": false
  }
}
```

## REST API

When the local API is running:

```bash
curl "http://127.0.0.1:8765/graph"
```

## Use Cases

- Inspect tag and project coverage.
- Find memories that reference a durable fact or policy.
- Feed a local visualization without adding a graph database.
- Decide whether a future graph store is justified by real usage.

## Performance

Run `ai-dememory index` before using graph-heavy workflows. The indexed path
avoids reparsing every Markdown file for each graph request and keeps `/graph`
fast for local dashboards.
