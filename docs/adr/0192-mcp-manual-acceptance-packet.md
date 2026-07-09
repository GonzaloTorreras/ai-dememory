# ADR 0192: MCP Manual Acceptance Packet

Status: Accepted

## Context

ADR 0186 added `ai-dememory acceptance packet` so release reviewers can get a
single generated handoff artifact for the manual v2 acceptance checks. MCP
clients could already inspect acceptance status, verification, plans, and
single-item templates, but they could not render the same full packet without
shelling out or writing a report file.

The current release blockers include manual acceptance evidence. Plugin and MCP
users need the packet content during review, but recording acceptance evidence
must remain a deliberate CLI action after human review.

## Decision

Expose read-only MCP tool `memory.acceptance_packet`.

The tool reuses the existing manual acceptance packet renderer and returns:

- completion counts;
- optional reviewer and PR URL handoff metadata;
- side-effect flags;
- `report_path=null`;
- the generated Markdown packet.

It sets `mutates_system=false`, `records_evidence=false`,
`writes_acceptance_records=false`, and `writes_files=false`. The returned
Markdown is secret-scanned before it leaves the server. The MCP tool never calls
`acceptance record`, never writes `reports/manual-acceptance-packet.md`, and
never creates files under `inbox/release-acceptance/`.

## Benefits

- MCP clients and Codex plugin skills can show the full release acceptance
  packet without requiring a shell command.
- Manual acceptance evidence remains human-reviewed and CLI-recorded.
- The implementation shares the CLI renderer, reducing drift between CLI and
  MCP packet content.
- Runtime smoke now exercises the packet through the same stdio tool path as
  real clients.

## Limitations

- The packet is a rendered planning aid, not acceptance evidence.
- MCP users still need to run `ai-dememory acceptance record` after reviewing
  real proof.
- Existing acceptance records are trusted as already secret-scanned input.
- The tool does not write or refresh the generated report file.
- Offset pagination can shift if acceptance evidence is recorded between page
  reads.

## Future Work

- ADR 0193 later adds the matching read-only MCP recall review packet renderer.
- Consider signed or externally verified manual acceptance records if reviewer
  identity needs stronger guarantees.
- Add section filters only if manual acceptance review needs more targeted
  packets.
- Add more structured release context only if packet handoffs need it.

## Dependencies

- ADR 0047 defines manual acceptance planning.
- ADR 0048 exposes manual acceptance planning over MCP.
- ADR 0080 defines single-item acceptance evidence templates.
- ADR 0186 defines the generated manual acceptance packet.
- ADR 0193 defines read-only MCP recall review packet rendering.
- ADR 0208 defines manual acceptance packet pagination.
- ADR 0209 defines optional manual acceptance packet metadata.
- `scripts/manual_acceptance.py` owns acceptance status, plans, templates, and
  packet rendering.
- `mcp/server/memory_mcp.py` exposes the read-only MCP tool.
