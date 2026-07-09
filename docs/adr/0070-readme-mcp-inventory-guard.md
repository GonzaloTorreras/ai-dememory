# ADR 0070: README MCP Inventory Guard

Status: Accepted for the v2 draft.

## Context

The main `README.md` is the first setup and distribution document most users
read. It includes the implemented MCP tool surface, while
`ai-dememory mcp-inventory --check-docs` previously guarded only the MCP gap
analysis plus the MCP-specific README files.

That left a drift risk: the server inventory, dedicated MCP docs, and plugin
configuration could be correct while the main README still advertised an old
tool count or omitted a newly added MCP tool. This matters for v2 because the
README is also the entry point for pip, Docker, plugin, and private-vault setup.

## Decision

Include `README.md` in the MCP inventory documentation guard.

The guard now requires README to:

- mention the current `<count> MCP tools` phrase
- mention every MCP tool name exposed by the server

`mcp/README.md` remains the detailed tool-description document and keeps the
same per-tool completeness check. The gap analysis and server README continue
to carry the current tool-count requirement.

## Benefits

- Keeps the main installation and distribution document aligned with the server
  inventory.
- Catches README drift during `mcp-inventory --check-docs`, `release-check`, and
  release evidence generation.
- Avoids relying on plugin docs or MCP-specific docs as substitutes for the
  user-facing landing page.

## Caveats

- The guard checks tool names and count, not prose quality or grouping.
- README can mention a tool name in a shallow list; detailed semantics remain in
  MCP-specific docs and ADRs.
- New tool additions must still update all relevant behavior docs, not only the
  README inventory list.

## Future Risks

- If generated documentation replaces hand-written inventory lists, this guard
  should move from name-presence checks to generated-block verification.
- If the server adds profile-specific tool sets, README may need separate
  installed, Docker, and plugin surface sections instead of one global list.
- If the README becomes too long for package landing pages, the guarded
  inventory may need to move to a compact generated table with links.

## Dependencies

- ADR 0010 defines the MCP inventory drift-checking pattern.
- ADR 0068 defines the guarded plugin MCP tool surface.
- ADR 0069 defines checked-in plugin MCP config smoke.
- `scripts/mcp_inventory.py` remains the source of truth for inventory doc
  validation.
