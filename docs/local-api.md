# Local REST API

`ai-dememory` includes a dependency-free local REST API for tools that cannot
launch MCP stdio but can call HTTP on localhost.

The API is local-first:

- Default bind: `127.0.0.1:8765`.
- No external dependencies or ASGI server.
- Non-loopback binds are refused unless `AI_DEMEMORY_API_KEY`, `--tls-cert`,
  and `--tls-key` are all present. There is no unauthenticated or cleartext
  network override.
- Responses default to public/internal memory only. Sensitive memory requires
  `include_sensitive=true`.

## Run

From a vault or tool checkout:

```bash
ai-dememory index
ai-dememory api --host 127.0.0.1 --port 8765
```

The `/search` and `/graph` endpoints are fastest after `ai-dememory index`.
`/graph` falls back to bounded Markdown parsing if no index exists and accepts
`limit`/`offset` pagination. MCP/API pages are capped at 100 memories; graph
nodes and edges have independent hard ceilings.

Smoke test the local API contract without touching your vault:

```bash
ai-dememory api-smoke
```

The smoke uses a temporary vault and verifies loopback health/search/graph,
default sensitive filtering, proposal inbox writes, reindexing, API-key
enforcement, and non-loopback bind refusal without an API key.

With an API key on loopback:

```bash
AI_DEMEMORY_API_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')" \
  ai-dememory api
```

Clients authenticate with either:

```text
X-API-Key: <key>
Authorization: Bearer <key>
```

For a deliberately network-bound instance, add a reviewed certificate and key:

```bash
AI_DEMEMORY_API_KEY="<random secret>" \
  ai-dememory api --host 192.0.2.10 --port 8765 \
  --tls-cert /protected/path/cert.pem --tls-key /protected/path/key.pem
```

## Endpoints

- `GET /health`
- `GET /search?query=<text>&limit=10`
- `GET /memories/{id}`
- `GET /graph?limit=10&offset=0`
- `POST /proposals`
- `POST /reindex`

Example:

```bash
curl "http://127.0.0.1:8765/search?query=codex&limit=3"
```

Proposal write:

```bash
curl -X POST "http://127.0.0.1:8765/proposals" \
  -H "Content-Type: application/json" \
  -d '{"title":"Session note","content":"Reviewed candidate memory.","tags":["session"]}'
```

## Safety Notes

Do not expose this API to a network without its required API key/TLS pair,
host firewalling, and a clear privacy model. It is not an OAuth or multi-user
service.

The REST search, memory and graph endpoints do not implement the fail-closed
`public_only` ceiling. Their default policy may return `public` and `internal`
metadata, so the API is not a safe recall surface for public-repository output.
Use bounded CLI or MCP context/search/get with `public_only=true` and an
explicit query for that workflow.

Use MCP stdio for LLM clients when possible. The REST API is for local tools,
dashboards, scripts, and experiments that need a stable HTTP surface.
