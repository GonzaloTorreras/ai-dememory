# ADR 0014: Generated MCP Client Config Smoke

## Status

Accepted for v2 draft.

## Context

The v2 checklist requires testing MCP behavior through real client
configuration, not only the repository's direct stdio smoke harness. Full GUI
client acceptance remains manual, but the generated config can be executed
automatically to prove that command, args, and environment wiring are coherent.

`ai-dememory mcp-config` previously emitted installed CLI and Docker command
fragments, but no automated gate launched those fragments.

## Decision

Add `ai-dememory mcp-client-smoke`, backed by
`scripts/mcp_client_smoke.py`.

The command either reads an MCP config JSON file or generates one with the same
logic as `ai-dememory mcp-config`, launches the configured command, sends MCP
`initialize` and `ping` requests over stdio, and verifies the expected
responses.

`ai-dememory mcp-config` now supports repeatable `--command-arg` values so a
local checkout can generate configs such as:

```bash
ai-dememory mcp-client-smoke --command python --command-arg scripts/ai_dememory.py
```

The default installed config remains `ai-dememory mcp --stdio`.

## Benefits

- Converts generated client config from documentation into executable evidence.
- Catches broken command, args, or `AI_DEMEMORY_ROOT` wiring before manual
  client testing.
- Lets package install smoke verify installed CLI config launch behavior.
- Keeps GUI MCP client acceptance manual and explicit.

## Limitations

- This does not prove a specific GUI client can discover or persist the config.
- Docker config smoke still requires Docker to be installed.
- The command checks lifecycle health only; broader tool behavior remains
  covered by `mcp-smoke`.

## Future Risks

- Client-specific config formats may diverge beyond the shared `mcpServers`
  shape.
- Windows command resolution differs from WSL/Linux and may need more examples
  as clients evolve.
- If remote MCP or OAuth is added later, stdio-only client config smoke will not
  be enough.
