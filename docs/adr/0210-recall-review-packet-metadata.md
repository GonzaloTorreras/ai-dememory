# ADR 0210: Recall Review Packet Metadata

Status: Accepted

## Context

ADR 0187 added generated recall review packets, ADR 0193 exposed the same
packet over MCP, and ADR 0207 added pagination for pending and malformed recall
miss sections. Those packets give reviewers a weekly fixture-review handoff,
but they could not pre-fill reviewer or pull request context.

Release and quality reviewers often attach recall review packets to PR comments
or local handoff notes. Re-entering reviewer and PR context manually creates
avoidable drift, while fixture promotion and miss closure must remain explicit
reviewed actions.

## Decision

Add optional reviewer and PR URL metadata to recall review packet rendering.

CLI:

- `ai-dememory recall-fixtures packet --reviewer "Reviewer Name" --pr-url https://github.com/... --write-report`

MCP:

- `memory.recall_review_packet` accepts `reviewer` and `pr_url`.

The packet payload and Markdown summary include:

- `reviewer`;
- `pr_url`;
- existing pagination fields from ADR 0207; and
- unchanged side-effect flags.

Blank metadata is normalized to `null` in JSON and rendered as `not provided`.
The rendered packet is still secret-scanned before writing or returning over
MCP. Metadata is handoff context only: it does not promote fixtures, close miss
files, write `quality/recall-fixtures.json`, or prove reviewer identity.

## Benefits

- Weekly recall review handoffs can carry reviewer and PR context directly in
  the generated packet.
- CLI and MCP packet output stay aligned through the shared renderer.
- The explicit `promote-miss` and `review-miss` boundaries remain unchanged.

## Limitations

- Reviewer identity is free text and is not signed or externally verified.
- PR URL syntax is not validated beyond rendered secret scanning.
- Existing generated packet files are not backfilled.

## Future Work

- Consider signed or externally verified recall review receipts if reviewer
  identity needs stronger guarantees.
- Add more structured release context only if recall handoffs need it.
- ADR 0212 adds CLI-only timestamped packet archives.

## Dependencies

- ADR 0187 defines the generated recall review packet.
- ADR 0193 defines read-only MCP recall review packet rendering.
- ADR 0207 defines recall review packet pagination.
- ADR 0212 defines recall review packet archives.
- `scripts/recall_fixtures.py` owns recall review packet rendering and secret
  scanning.
- `mcp/server/memory_mcp.py` exposes MCP packet metadata fields.
