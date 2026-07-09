# ADR 0115: Recall Review Plan Report

## Status

Accepted.

## Context

Recall review planning is available through CLI, MCP, and release evidence, but
weekly review still lacked a standalone file artifact that a reviewer could
inspect, attach to manual evidence, or compare across local runs.

`reports/` is already the generated-artifact location for release evidence,
vector readiness, durable provenance, lifecycle, and maintenance reports. A
recall review report fits that model as long as it remains generated and does
not mutate recall fixtures or canonical memory.

## Decision

Add `ai-dememory recall-fixtures review-plan --write-report`.

The command writes `reports/recall-review-plan.md` by default and accepts
`--report-path` for another in-vault generated report path. The report renders
the existing read-only review plan:

- fixture freshness summary
- pending recall misses
- invalid recall miss files
- bounded recent resolved misses
- next actions
- explicit boundaries

The command rejects report paths outside the vault.
The final rendered report is secret-scanned before writing.

## Benefits

- Gives weekly recall review a concrete generated artifact.
- Makes manual release evidence easier to collect without recording false
  acceptance.
- Reuses the same recall review plan object used by CLI, MCP, and release
  evidence.
- Keeps review actions separate from report generation.

## Limitations

- The report is generated and should not be treated as canonical memory.
- Writing the report does not satisfy the reviewed recall-promotion freshness
  gate.
- The report shows a bounded recent resolved sample, not every resolved miss.
- Secret scanning can reject the report if future rendered fields contain
  secret-like text.

## Future Risks

- If recall review reports become long-lived evidence, they may need timestamped
  output paths instead of overwriting the latest report.
- If resolved-miss history needs complete audit export, the report may need
  pagination or a separate archive command.
- If report files are accidentally staged, the generated-artifact guard should
  continue blocking them.
- If new report sections include raw recall miss excerpts, the rendered-output
  scan must stay after all sections are assembled.

## Dependencies

- ADR 0045 defines recall fixture review planning.
- ADR 0111 embeds recall review planning in release evidence.
- ADR 0114 adds resolved recall miss summaries.
- ADR 0126 documents rendered secret scanning for recall review reports.
- `scripts/recall_fixtures.py` owns report rendering and path validation.
- `scripts/artifact_guard.py` treats `reports/` as generated output.
