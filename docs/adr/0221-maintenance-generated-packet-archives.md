# ADR 0221: Maintenance Generated Packet Archives

Status: Accepted

## Context

ADR 0218 added read-only retention plans for generated recall review and manual
acceptance packet archives. ADR 0220 exposed compact archive cleanup pressure in
setup health and release evidence. Routine maintenance status and generated
maintenance reports still did not include that signal, so scheduled users had
to run separate archive commands to notice growing generated packet archives.

Maintenance is already the local weekly surface for generated reports, recall
quality checks, hook capture review, and review queue summaries. It should show
generated packet archive pressure without turning retention planning into
automatic deletion.

## Decision

Add a compact `generated_packet_archives` summary to:

- `ai-dememory maintenance status`;
- MCP `memory.maintenance_status`;
- `ai-dememory maintenance run --profile <daily|weekly>` results; and
- generated maintenance reports.

The summary reuses the same read-only archive status and retention-plan helpers
used by setup health. It reports total and prunable generated packet archives
across recall review and manual acceptance packet archive directories, plus
per-kind compact counts and latest snapshot metadata.

Maintenance dry-runs also expose `would_review_generated_packet_archives=true`
and `would_delete_generated_packet_archives=false`.

## Benefits

- Scheduled maintenance reviewers can see generated packet archive cleanup
  pressure in the same status and report surfaces they already inspect.
- MCP clients can present cleanup guidance from `memory.maintenance_status`
  without running separate archive status tools.
- The archive retention model remains review-first and side-effect explicit.

## Limitations

- Maintenance does not delete, move, or compress generated packet archives.
- The summary uses the default retention policy from the retention-plan
  commands.
- Large archive histories are summarized with counts and latest metadata rather
  than listed in full.

## Future Risks

- If retention policy becomes configurable, maintenance status must report the
  active policy source.
- If archive directories become very large, maintenance may need a generated
  archive index before scanning them on every status call.
- If an approval-gated pruning command is added later, maintenance must keep
  automatic deletion opt-in rather than silently pruning scheduled archives.

## Dependencies

- ADR 0154 defines maintenance profile dry-run behavior.
- ADR 0218 defines generated packet archive retention plans.
- ADR 0220 adds setup-health generated packet archive summaries.
- `scripts/maintenance.py` owns maintenance status and reports.
- `mcp/server/memory_mcp.py` exposes `memory.maintenance_status`.
