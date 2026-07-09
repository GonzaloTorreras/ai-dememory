# ADR 0166: Review Report Policy Metadata

Status: Accepted

## Context

ADR 0165 added compact `enabled` and `policy` metadata to CLI JSON and MCP
review listing responses. Generated Markdown reports still had the older
human-oriented shape, so an archived report with no candidates did not show
whether the workflow was disabled or enabled and empty.

Offline review evidence should carry enough policy context to be understood
without making an extra `review modes`, `review plan`, JSON, or MCP call.

## Decision

Add a compact `Review Policy` section to generated Markdown reports for:

- `ai-dememory review false-positives`;
- `ai-dememory review stale-false-positives`; and
- `ai-dememory review conflicts`.

The section includes the workflow `enabled` state and the relevant compact
policy fields already exposed by ADR 0165. Report writers attach metadata from
the vault root. Direct renderer calls remain backward compatible when metadata
is omitted.

## Benefits

- Archived review reports can distinguish disabled workflows from empty enabled
  queues.
- Markdown reports, CLI JSON, and MCP review listing responses now carry the
  same compact policy signal.
- The change is additive and does not alter review scanning, report paths,
  secret scanning, or review-state writes.

## Limitations

- The section is a policy snapshot at report generation time.
- The section is intentionally compact; full cross-workflow policy still lives
  in `review modes` and `review plan`.
- Write receipts remain focused on the performed audit action and do not repeat
  policy metadata.

## Future Work

- Link generated reports to the review plan output if report bundles need fuller
  cleanup guidance.
- Add policy metadata to any future review report type by reusing the shared
  renderer helper.

## Dependencies

- ADR 0161 defines review policy defaults.
- ADR 0162 enforces enabled review workflow boundaries.
- ADR 0165 adds compact review policy metadata to JSON and MCP list responses.
- `scripts/review_memory.py` owns generated Markdown review reports.
