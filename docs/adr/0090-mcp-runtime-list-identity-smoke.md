# ADR 0090: MCP Runtime List Identity Smoke

## Status

Accepted.

## Context

ADR 0089 made the PR-gated MCP runtime smoke follow pagination for
`tools/list`, `resources/list`, and `prompts/list`. The smoke then checked
expected names against sets, which proved expected items existed but could hide
duplicate identities across pages.

Duplicate tool names, resource URIs, or prompt names would make client behavior
ambiguous and could mask server inventory drift during release review.

## Decision

Update `scripts/mcp_runtime_smoke.py` so paginated MCP list responses must use
unique stable identities:

- `tools/list`: unique non-empty `name`
- `resources/list`: unique non-empty `uri`
- `prompts/list`: unique non-empty `name`

The shared pagination collector now also rejects non-object list entries instead
of silently dropping malformed items before identity validation.

## Benefits

- Catches duplicate MCP surface entries before release readiness is claimed.
- Makes paginated smoke output stricter without expanding the manual acceptance
  burden.
- Keeps tool, resource, and prompt identity checks close to the runtime behavior
  that clients consume.

## Limitations

- The smoke validates list identities, not semantic equivalence of duplicate
  tool schemas or resource content.
- It does not enforce global identity uniqueness between different list methods.
- It assumes `name` and `uri` remain the server's stable MCP identity fields.

## Future Risks

- If MCP resource identity changes away from `uri`, this smoke should be updated
  with the server contract.
- If aliases or localized labels are added, they should not replace the stable
  identity fields validated here.
- If a future client allows duplicate display names with distinct ids, this ADR
  should be revisited before relaxing runtime smoke checks.

## Dependencies

- ADR 0021 defines broad PR-gated MCP runtime smoke coverage.
- ADR 0089 defines paginated runtime list traversal.
- `mcp/server/memory_mcp.py` remains the source of MCP list item shape.
- `scripts/mcp_runtime_smoke.py` remains the PR-gated stdio runtime smoke.
