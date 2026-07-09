# ADR 0205: MCP Review Recommendation Outcome Report

Status: Accepted

## Context

ADR 0204 added the CLI-generated review recommendation outcome sign-off report
under `reports/review-recommendation-outcomes.md`. That report gives reviewers
an offline Markdown packet before archiving accepted or rejected advisory
recommendations.

Codex and other local MCP clients can already inspect recommendation status and
record outcomes, but they could not render the same outcome packet without
calling the CLI or writing a generated report file.

## Decision

Expose read-only MCP tool `memory.review_recommendation_outcome_report`.

The tool accepts:

- optional `kind`;
- `outcome_status` of `reviewed`, `accepted`, or `rejected`;
- `limit`;
- `offset`; and
- `invalid_offset`.

It reuses the CLI outcome report payload and Markdown renderer, but returns the
packet directly over MCP with:

- `writes_files=false`;
- `applies_review_decisions=false`;
- `writes_canonical_memory=false`;
- `report_path=null`;
- structured counts, pagination fields, recommendation records, malformed
  artifacts, next actions; and
- rendered Markdown.

The tool is added to the Codex plugin `enabled_tools` allowlist and covered by
runtime smoke.

## Benefits

- MCP clients can present the same sign-off packet as the CLI report without
  writing `reports/`.
- Reviewers can inspect accepted/rejected recommendation outcomes inside Codex
  before archival.
- The server keeps one report implementation for CLI and MCP rendering.
- The tool follows the existing read-only packet pattern for recall, manual
  acceptance, and release evidence reports.

## Limitations

- MCP rendering does not persist evidence; use the CLI report command when a
  generated file is needed.
- The tool does not apply recommendations, archive artifacts, or mutate
  canonical memory.
- Offset pagination can shift if active recommendation artifacts change between
  page reads.

## Future Work

- Add section filters if reviewed recommendation outcome volume needs more
  targeted packets.
- Include archived outcome history only if reviewers need one packet spanning
  active and archived recommendation artifacts.

## Dependencies

- ADR 0191 defines recommendation outcome status.
- ADR 0204 defines the CLI outcome report payload and Markdown renderer.
- ADR 0206 defines outcome report pagination.
- `scripts/review_memory.py` owns the shared report implementation.
- `mcp/server/memory_mcp.py` exposes the read-only MCP tool.
- `scripts/mcp_runtime_smoke.py` verifies stdio behavior.
