# ADR 0046: MCP Recall Review Plan

## Status

Accepted for the v2 draft.

## Context

ADR 0045 added `ai-dememory recall-fixtures review-plan` so weekly recall
quality review can see fixture freshness, pending miss files, malformed miss
files, and next actions in one read-only command. MCP clients could already
capture misses and inspect fixture freshness with `memory.capture_miss` and
`memory.recall_fixture_status`, but they still could not inspect the combined
pending-review plan without shelling out to the CLI.

That left Codex plugin and MCP-only workflows able to create review work but
unable to summarize the pending recall review queue.

## Decision

Expose `memory.recall_review_plan` as a read-only MCP tool.

The tool reuses the same evaluator as the CLI command and returns:

- fixture freshness;
- pending `inbox/recall-feedback/` miss files;
- malformed miss files;
- next review actions.

It accepts bounded `max_age_days` input. It does not promote misses, write
fixtures, create embeddings, or mutate canonical memory.

## Benefits

- Lets MCP clients complete the recall-quality review loop without launching a
  shell.
- Keeps the CLI and MCP review-plan outputs backed by one implementation.
- Makes pending recall misses visible in runtime smoke after `memory.capture_miss`.

## Limitations

- The tool reports review work; it does not decide whether a miss is valid.
- Promotion stays CLI-only to preserve explicit reviewed provenance inputs.
- The output depends on local Markdown inbox files and may be empty on fresh
  vaults.

## Future Risks

- If MCP clients need to promote reviewed misses, a separate tool would need a
  stricter reviewer identity and provenance design.
- If recall miss schemas grow, the MCP output contract may need versioning.
- If pending miss files contain unusual secret formats, redaction remains
  dependent on the shared secret scanner patterns.

## Dependencies

- ADR 0017 defines reviewed recall miss promotion.
- ADR 0035 exposes recall fixture freshness over MCP.
- ADR 0045 defines the shared recall review-plan evaluator.
