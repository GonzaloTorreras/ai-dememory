# ADR 0220: Setup Health Generated Packet Archives

Status: Accepted

## Context

ADR 0218 added read-only retention plans for generated manual acceptance and
recall review packet archives. ADR 0219 made those preview commands
discoverable through setup plans. Operators can now find and run retention
previews, but `ai-dememory setup health --json` and MCP `memory.setup_health`
do not summarize whether generated packet archives exist or whether any are
cleanup candidates.

Setup health is the combined passive status surface used by setup docs,
plugins, MCP clients, and release handoffs. It should show enough generated
packet archive state to guide reviewers without listing large archive histories
or deleting files.

## Decision

Add `generated_packet_archives` to setup health.

The section summarizes:

- total generated packet archives across recall review and manual acceptance
  packet archive directories;
- prunable archive count from the read-only retention plans;
- per-kind archive roots, total counts, retained counts, prunable counts, and
  latest generated snapshot metadata; and
- explicit side-effect flags showing `writes_files=false` and
  `deletes_files=false`.

Release evidence embeds a compact `generated_packet_archives` object in
`setup_health_summary` and renders the prunable count in the Markdown handoff.

## Benefits

- First-run and release handoff surfaces can show generated packet archive
  cleanup pressure without requiring separate commands.
- MCP clients can present retention guidance from one setup-health read.
- The setup-health contract remains passive and keeps generated archives
  separate from reviewed acceptance evidence and recall fixture promotions.

## Limitations

- Setup health only reports compact counts and the latest archive metadata; it
  does not list every archive.
- It reuses the default retention policy from the retention-plan commands.
- It does not delete, move, or compress generated packet archives.

## Future Risks

- If retention policy becomes configurable, setup health must report the active
  policy source.
- If archive directories become very large, the latest-entry lookup may need a
  generated index rather than direct directory scans.
- If an approval-gated deletion command is added, setup health must continue to
  avoid returning destructive commands as default actions.

## Dependencies

- ADR 0153 defines setup health as the passive local setup status surface.
- ADR 0185 embeds setup health in release evidence.
- ADR 0218 defines generated packet archive retention plans.
- ADR 0219 exposes generated archive retention commands in setup plans.
- `scripts/setup_plan.py` owns setup health assembly.
- `scripts/release_evidence.py` owns release evidence summary rendering.
