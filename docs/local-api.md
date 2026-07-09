# Local REST API

`ai-dememory` includes a dependency-free local REST API for tools that cannot
launch MCP stdio but can call HTTP on localhost.

The API is local-first:

- Default bind: `127.0.0.1:8765`.
- No external dependencies or ASGI server.
- Non-loopback binds are refused unless `AI_DEMEMORY_API_KEY` is set or the
  caller explicitly passes `--allow-unauthenticated-network`.
- Responses default to public/internal memory only. Sensitive memory requires
  `include_sensitive=true`.

## Run

From a vault or tool checkout:

```bash
ai-dememory index
ai-dememory api --host 127.0.0.1 --port 8765
```

The `/search` and `/graph` endpoints are fastest after `ai-dememory index`.
`/graph` falls back to Markdown parsing if no index exists.

Smoke test the local API contract without touching your vault:

```bash
ai-dememory api-smoke
```

The smoke uses a temporary vault and verifies loopback health/search/graph,
default sensitive filtering, proposal inbox writes, reindexing, API-key
enforcement, and non-loopback bind refusal without an API key.

With an API key:

```bash
AI_DEMEMORY_API_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')" \
  ai-dememory api
```

Clients authenticate with either:

```text
X-API-Key: <key>
Authorization: Bearer <key>
```

## Endpoints

- `GET /health`
- `GET /search?query=<text>&limit=10`
- `GET /memories/{id}`
- `GET /graph`
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

Do not expose this API to a network without an API key, host firewalling, and a
clear privacy model. It is not an OAuth or multi-user service.

Use MCP stdio for LLM clients when possible. The REST API is for local tools,
dashboards, scripts, and experiments that need a stable HTTP surface.
