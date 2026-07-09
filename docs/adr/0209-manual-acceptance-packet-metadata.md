# ADR 0209: Manual Acceptance Packet Metadata

Status: Accepted

## Context

ADR 0186 added generated manual acceptance packets, ADR 0192 exposed the same
packet over MCP, and ADR 0208 added pagination for incomplete acceptance items.
Those packets were useful as review checklists, but they could not pre-fill the
reviewer or pull request context for a release handoff.

Release reviewers often attach packet output to PR comments or local handoff
notes. Repeating reviewer and PR context manually makes handoffs more error
prone, while recording actual acceptance evidence must remain an explicit
reviewed action.

## Decision

Add optional reviewer and PR URL metadata to manual acceptance packet rendering.

CLI:

- `ai-dememory acceptance packet --reviewer "Reviewer Name" --pr-url https://github.com/... --write-report`

MCP:

- `memory.acceptance_packet` accepts `reviewer` and `pr_url`.

The packet payload and Markdown summary include:

- `reviewer`;
- `pr_url`;
- existing pagination fields from ADR 0208; and
- unchanged side-effect flags.

Blank metadata is normalized to `null` in JSON and rendered as `not provided`.
The rendered packet is still secret-scanned before writing or returning over
MCP. Metadata is handoff context only: it does not record acceptance evidence,
does not alter acceptance records, and does not prove reviewer identity.

## Benefits

- PR and release handoffs can carry reviewer and PR context directly in the
  generated packet.
- CLI and MCP packet output remain aligned through the shared renderer.
- Metadata remains non-authoritative, preserving the explicit
  `acceptance record` boundary.

## Limitations

- Reviewer identity is free text and is not signed or externally verified.
- PR URL syntax is not validated beyond rendered secret scanning.
- Existing generated packet files are not backfilled.

## Future Work

- Consider signed or externally verified manual acceptance records if reviewer
  identity needs stronger guarantees.
- Add more structured release context only if real handoffs need it.
- ADR 0211 adds CLI-only timestamped packet archives.

## Dependencies

- ADR 0186 defines the generated manual acceptance packet.
- ADR 0192 defines read-only MCP manual acceptance packet rendering.
- ADR 0208 defines manual acceptance packet pagination.
- ADR 0211 defines manual acceptance packet archives.
- `scripts/manual_acceptance.py` owns acceptance packet rendering and secret
  scanning.
- `mcp/server/memory_mcp.py` exposes MCP packet metadata fields.
