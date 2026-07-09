# ADR 0116: Manual Acceptance Plan Report

## Status

Accepted.

## Context

Manual acceptance planning is available through CLI, MCP, and release evidence,
but release handoffs still lacked a standalone file artifact that lists the
remaining checks, suggested proof, and record commands without pretending the
manual work is complete.

`reports/` is already the generated-artifact location for release evidence,
recall review plans, durable provenance, lifecycle, and maintenance reports. A
manual acceptance plan report fits that model as long as it remains generated
and does not record acceptance evidence.

## Decision

Add `ai-dememory acceptance plan --write-report`.

The command writes `reports/manual-acceptance-plan.md` by default and accepts
`--report-path` for another in-vault generated report path. The report renders
the existing read-only acceptance plan:

- completion summary
- remaining manual acceptance items
- blocked manual acceptance items
- completed manual acceptance items
- suggested evidence artifacts
- latest reviewed record, when present
- pass and block record commands
- next actions
- explicit boundaries

The command rejects report paths outside the memory root.
The rendered report is secret-scanned before writing.

## Benefits

- Gives manual release acceptance a concrete generated planning artifact.
- Makes reviewer handoffs easier without recording false evidence.
- Reuses the same planner object used by CLI, MCP, and release evidence.
- Keeps evidence recording separate from report generation.
- Avoids copying secret-like reviewed record text into a generated report.

## Limitations

- The report is generated and should not be treated as canonical memory.
- Writing the report does not satisfy manual acceptance.
- The report overwrites the default path on each run.

## Future Risks

- If manual acceptance reports become audit evidence, they may need timestamped
  output paths instead of overwriting the latest report.
- If manual acceptance moves outside Markdown records, the report renderer must
  follow the new evidence source.
- If report files are accidentally staged, the generated-artifact guard should
  continue blocking them.

## Dependencies

- ADR 0016 defines manual acceptance evidence records.
- ADR 0047 defines manual acceptance planning.
- ADR 0049 embeds manual acceptance planning in release evidence.
- ADR 0058 adds suggested evidence artifacts.
- `scripts/manual_acceptance.py` owns report rendering and path validation.
- `scripts/artifact_guard.py` treats `reports/` as generated output.
