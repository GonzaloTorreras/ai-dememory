# Local REST API

The optional REST API gives a local dashboard or script an HTTP interface to a
separately bound private vault. It is not part of installation, and it is not
the MCP server used by an AI client.

Start with the [installation guide](install.md): install the `ai-dememory` CLI
and create a private vault outside this public source repository. The command
name is `ai-dememory`; a source-checkout wrapper is a maintainer-only fallback,
not the normal way to run the API.

The API requires an explicit absolute `--root <vault>` (or `~` path after home
expansion) or `AI_DEMEMORY_ROOT` runtime binding. It never searches the current
directory or source checkout for a vault; an explicit non-empty `--root` takes
precedence over the environment.

## Choose The Right Local Interface

| Need | Use |
| --- | --- |
| An AI client such as Codex or Claude | [Local MCP](local-mcp.md) over stdio |
| A local dashboard or script that can call loopback HTTP without a cross-origin browser request | This loopback REST API |
| No local HTTP consumer | Skip the API entirely |

The current unreleased 2.1.1rc2 source line's operational wizard may show the
API command as an optional next action for dashboards and scripts. It never
starts a server, edits a client configuration, or creates a schedule for it.
That source candidate is not an additional package-install route: use a
published package before following this guide.

The API serves JSON only and emits no CORS headers, so a browser page served
from another origin cannot call it directly. An advanced local UI can use a
same-origin reverse proxy only when it keeps a loopback `Host`
(`127.0.0.1` or `localhost`) and forwards a matching `Origin`; this project
does not configure or support that proxy or its browser-auth design. For the
normal path, use a native/local script instead.

## Start A Bound Loopback Server

Use the installed CLI and name the intended private vault explicitly. Build the
index before using `/search`; `/graph` can operate without it, but the index
makes both search and graph responses faster:

```bash
ai-dememory --root ~/code/my-memory index
ai-dememory --root ~/code/my-memory api
```

The default bind is `http://127.0.0.1:8765`. The process stays in the foreground
and stops with `Ctrl-C`; it does not install a background service or scheduler.
Make that default bind explicit for a script, or choose a different loopback
port when you need one:

```bash
ai-dememory --root ~/code/my-memory api --host 127.0.0.1 --port 8765
```

`/graph` can fall back to bounded Markdown parsing without an index. HTTP
`/search` and `/graph` requests accept at most 50 memories per page, and graph
nodes and edges have independent hard ceilings.

## Authentication And Network Binding

Loopback use can take an API key when the local client needs an explicit shared
secret:

```bash
AI_DEMEMORY_API_KEY="<generated-local-secret>" \
  ai-dememory --root ~/code/my-memory api
```

Clients may use either `X-API-Key: <key>` or `Authorization: Bearer <key>`.
Keep a real key outside the vault and repository.

A non-loopback bind is an advanced deployment decision, not a normal local
setup. It is refused unless an API key and both TLS paths are supplied:

```bash
AI_DEMEMORY_API_KEY="<generated-local-secret>" \
  ai-dememory --root ~/code/my-memory api --host 192.0.2.10 --port 8765 \
  --tls-cert /protected/path/cert.pem --tls-key /protected/path/key.pem
```

Also apply host firewalling and define a privacy model before exposing the API.
It is not an OAuth or multi-user service.

## HTTP Surface

- `GET /health`
- `GET /search?query=<text>&limit=10`
- `GET /memories/{id}`
- `GET /graph?limit=10&offset=0`
- `POST /proposals`
- `POST /reindex`

For example:

```bash
curl "http://127.0.0.1:8765/search?query=codex&limit=3"
```

`POST /proposals` writes a review candidate, not durable memory. A mutation
also requires the explicit local-write intent header (and the API key when one
is configured):

```bash
curl -X POST "http://127.0.0.1:8765/proposals" \
  -H "Content-Type: application/json" \
  -H "X-AI-DeMemory-Intent: reviewed-local-write" \
  -d '{"title":"Session note","content":"Reviewed candidate memory.","tags":["session"]}'
```

## Privacy Boundary

REST search, memory, and graph endpoints default to public and internal memory;
private or sensitive memory requires `include_sensitive=true`. They do not
implement the fail-closed `public_only` ceiling, so do not use this API as a
public-repository recall surface. For bounded public context, use the CLI or MCP `context`,
`search`, and `get` operations with `public_only=true`.

## Maintainer Or Support Verification

`api-smoke` creates a temporary vault and validates loopback health/search/
graph, proposal inbox writes, reindexing, API-key handling, and non-loopback
refusal. It is a development/support check, not a first-run step:

```bash
ai-dememory dev api-smoke
```
