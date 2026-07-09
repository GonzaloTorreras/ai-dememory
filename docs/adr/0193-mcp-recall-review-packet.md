# ADR 0193: MCP Recall Review Packet

Status: Accepted

## Context

ADR 0187 added `ai-dememory recall-fixtures packet` so reviewers can inspect a
weekly recall-quality handoff before promoting real retrieval misses into
`quality/recall-fixtures.json`. MCP clients already had structured recall
status, candidate checking, review planning, and miss review tools, but not the
same full Markdown packet used by CLI reviewers.

The current v2 release blockers include a reviewed recall promotion from a real
retrieval miss. Plugin and MCP workflows need the same packet guidance while
keeping fixture promotion and miss closure explicit, reviewed actions.

## Decision

Expose read-only MCP tool `memory.recall_review_packet`.

The tool reuses `recall_fixture_review_plan` and `render_recall_review_packet`.
It accepts the same bounded review planning arguments:

- `max_age_days`
- `resolved_limit`

The response includes recall review counts, side-effect flags,
`report_path=null`, and the rendered Markdown packet. It always reports:

- `mutates_system=false`
- `records_fixture_promotions=false`
- `writes_fixture_file=false`
- `closes_miss_files=false`
- `writes_files=false`

The rendered Markdown is secret-scanned before being returned. The MCP tool
does not write `reports/recall-review-packet.md`, does not update
`quality/recall-fixtures.json`, and does not mark miss files reviewed.

## Benefits

- MCP clients and Codex plugin skills can show the same recall review handoff as
  the CLI without shelling out.
- Review guidance remains separate from reviewed promotion or rejection.
- Runtime smoke exercises the packet through the stdio MCP path used by real
  clients.
- The implementation shares the CLI renderer, reducing drift between CLI and
  MCP packet content.

## Limitations

- The packet is guidance only and does not satisfy recall-quality release
  evidence.
- A reviewer still must promote a real miss with
  `ai-dememory recall-fixtures promote-miss` or close it with
  `recall-fixtures review-miss` / `memory.recall_miss_review`.
- Offset pagination can shift if recall miss files are added or reviewed
  between page reads.

## Future Work

- Add section filters if recall miss volume needs more targeted packets.
- ADR 0210 adds optional reviewer and PR URL packet metadata.
- ADR 0212 adds CLI-only timestamped packet archives.

## Dependencies

- ADR 0034 defines recall fixture freshness status.
- ADR 0045 defines the recall fixture review plan.
- ADR 0046 exposes recall review planning over MCP.
- ADR 0113 defines rejected and dismissed miss outcomes.
- ADR 0187 defines the CLI recall review packet.
- ADR 0207 defines recall review packet pagination.
- ADR 0210 defines optional recall review packet metadata.
- ADR 0212 defines recall review packet archives.
- `scripts/recall_fixtures.py` owns recall review planning and packet rendering.
- `mcp/server/memory_mcp.py` exposes the read-only MCP tool.
