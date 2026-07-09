# ADR 0173: MCP Hook Capture Review

## Status

Accepted

## Context

ADR 0172 added CLI hook capture review receipts so reviewers can close
`inbox/session-events/` candidates without hand-editing Markdown. Plugin review
flows need the same lifecycle closure from inside MCP clients, but the tool must
stay review-first: no durable promotion, no deletion, no raw provider-folder
reads, and no writes outside the hook capture inbox.

## Decision

Add MCP tool `memory.hook_capture_review`. The tool accepts:

- `path`
- `status`
- `reviewed_by`
- `reason`

The status is one of `reviewed`, `rejected`, or `dismissed`. The MCP handler
reuses the same `review_hook_capture` helper as the CLI, so it path-bounds the
selected Markdown file to `inbox/session-events/`, validates hook-capture
frontmatter, rejects already resolved captures, secret-scans receipt metadata,
and writes only review receipt fields.

The response is a structured receipt with `path`, `review_status`,
`reviewed_by`, `reviewed_at`, `reason`, and
`canonical_memory_updated=false`. The tool is included in the Codex plugin MCP
allowlist and is annotated as non-destructive but not read-only, so clients can
keep it approval-gated.

## Benefits

- Plugin reviewers can close hook capture candidates without leaving the MCP
  workflow.
- CLI and MCP review receipts share validation and secret-scan behavior.
- Review-due counts clear in `memory.hook_status` after the receipt is recorded.
- Canonical durable memory remains a separate human-reviewed promotion step.

## Limitations

- This does not promote hook capture content into canonical memory.
- This does not delete, archive, or move reviewed hook capture files.
- This does not add automatic filters for high-volume hook capture review.

## Future Risks

- MCP clients may ask for archive support, but moving files should remain a
  separate approval-gated decision from recording review receipts.

## Dependencies

- ADR 0172 defines hook capture review receipt fields.
- `scripts/hook_event.py` owns receipt validation and writes.
- `mcp/server/memory_mcp.py` exposes the MCP tool contract.
- `plugins/ai-dememory/.mcp.json` allowlists the plugin tool.
