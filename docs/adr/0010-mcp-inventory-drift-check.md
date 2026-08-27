# ADR 0010: MCP Inventory Drift Check

## Status

Accepted for v2 draft.

## Context

The MCP server surface has grown from the original search/read/proposal tools
into a larger local-memory interface. Human-maintained docs drifted from the
actual server implementation and undercounted the exposed tools.

The v2 release depends on users being able to install the tool as a package,
run it as a local MCP server, and understand what operations clients may call.
Incorrect MCP inventory docs create setup friction and hide review/safety
boundaries.

## Decision

Add `ai-dememory mcp-inventory` backed by `scripts/mcp_inventory.py`.

Default and `--profile` output load the canonical server definitions from the
active package and report:

- supported protocol versions
- server capabilities
- tool count and tool names
- prompts
- resource templates

Those reporting branches are package/rootless. They do not resolve a vault,
read `AI_DEMEMORY_ROOT`, inspect the saved selector, or discover the current
working directory. A legacy nonempty `--root` is accepted but ignored there.

`ai-dememory mcp-inventory --check-docs` verifies that the MCP gap analysis,
root MCP README, server README, and inventory-related ADRs mention the current
`74 MCP tools` inventory, and that the root MCP README lists every tool name.
This separate source-bound branch reads only the checkout containing the direct
script or an explicit absolute `--root`; vault selectors and CWD are never
source authority. `release-check` fails when that documentation drifts.

## Benefits

- Keeps install and MCP setup docs aligned with the implementation.
- Turns a manual v2 review item into an automated release gate.
- Makes future tool additions safer because docs must be updated in the same PR.
- Gives reviewers a quick inventory command without starting an MCP client.

## Limitations

- The checker validates names and the explicit count, not full prose quality.
- It does not prove that every tool behaves correctly; runtime smoke tests cover
  representative behavior separately.
- It does not query external MCP documentation.
- An installed wheel can always report package inventory. Documentation
  validation requires a source checkout and is not an installed-vault command.

## Future Risks

- Tool aliases or generated docs could make name checks too rigid.
- If the MCP server moves to an SDK, the inventory loader may need to follow new
  registration APIs.
- Registry metadata, MCP Apps, or Tasks support would require a broader
  distribution inventory beyond local stdio tools.
