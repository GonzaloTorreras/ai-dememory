# ADR 0082: MCP Review Mode Configuration

## Status

Accepted.

## Context

Review modes control how much assistance an LLM may provide during inbox,
false-positive, conflict, maintenance, and promotion review. The CLI already
supports `ai-dememory review configure-mode --mode <mode>`, while MCP clients
could only inspect `memory.review_modes` and `memory.review_plan`.

That made MCP workflows depend on shelling out to change local review policy,
even though the change is limited to `.ai-dememory.toml` and does not edit
canonical memory.

## Decision

Expose `memory.review_configure_mode` as an MCP tool.

The tool writes the active review mode through the existing
`configure_review_mode` implementation. It returns a structured receipt with
the config path, requested mode, active canonical mode, reviewer, built-in
policy flags, and `canonical_memory_updated=false`.

The tool is a configuration write, not a memory write. It does not promote,
delete, archive, supersede, or rewrite Markdown memory.

## Benefits

- Lets MCP clients complete the review-policy setup loop without shelling out.
- Keeps CLI and MCP behavior backed by one implementation.
- Makes the active policy and safety flags visible immediately after writing.
- Preserves human review requirements for durable and canonical memory changes.

## Limitations

- The tool trusts the MCP client's approval UX for the configuration write.
- It only supports built-in modes and aliases, not custom policy definitions.
- It does not prove that future LLM behavior will follow the configured mode;
  command-level gates and review discipline still matter.

## Future Risks

- If custom review modes are added, the input schema and receipt may need a
  version field.
- If remote MCP deployment is introduced later, review-mode writes may need
  stronger authentication and audit metadata.
- If clients expose one-click mode changes, they should show the policy flags
  before calling the tool.

## Dependencies

- ADR 0002 defines the built-in review modes.
- ADR 0027 defines canonical mode names and the `batch` alias behavior.
- `scripts/review_memory.py` remains the source of review-mode configuration.
