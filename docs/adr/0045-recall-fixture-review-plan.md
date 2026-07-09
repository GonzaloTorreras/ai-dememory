# ADR 0045: Recall Fixture Review Plan

## Status

Accepted for the v2 draft.

## Context

The v2 memory-quality loop requires recall fixtures to grow from reviewed real
misses. ADR 0034 added fixture freshness status, and ADR 0017 added reviewed
miss promotion. Reviewers still had to manually inspect
`inbox/recall-feedback/` to know which miss files were pending or malformed
before promotion.

That manual scan is easy to skip during weekly maintenance and makes it harder
to distinguish seed-only fixture sets from real pending review work.

## Decision

Add `ai-dememory recall-fixtures review-plan`.

The command is read-only. It combines fixture freshness with pending
`inbox/recall-feedback/` miss files, malformed miss files, and next actions for
weekly review. It supports `--json` for automation and text output for humans.

Secret-like frontmatter fields in pending miss files are redacted in output
rather than echoed back to the terminal.

## Benefits

- Gives reviewers one command for weekly recall miss triage.
- Keeps promotion review-first by listing pending work without mutating
  `quality/recall-fixtures.json`.
- Makes malformed recall miss files visible before release or maintenance
  sign-off.
- Provides package install smoke coverage for the recall review path.

## Limitations

- The command does not decide whether a miss should be promoted; human review is
  still required.
- It does not validate that expected memory ids exist, because promotion remains
  the write-time validation gate.
- Secret redaction is pattern-based and complements, but does not replace,
  `ai-dememory secret-scan`.

## Future Risks

- If recall misses gain richer schemas, the review plan output may need versioned
  fields.
- If MCP clients need this plan directly, a read-only MCP tool should share the
  same evaluator instead of duplicating logic.
- If fixture review moves to an external tracker, path-based inbox reporting may
  need an adapter.

## Dependencies

- ADR 0017 defines reviewed recall miss promotion.
- ADR 0034 defines recall fixture freshness status.
- ADR 0036 keeps vector search gated on measured recall fixture failures.
