# ADR 0125: Maintenance Report Directory Guard

## Status

Accepted.

## Context

`ai-dememory maintenance run` writes timestamped generated Markdown reports
under `reports/maintenance/`. Other v2 generated report writers now validate
custom paths and scan rendered output before writing. Maintenance reports did
not expose a configurable report directory, and the rendered report was written
without a final output scan.

Maintenance reports can include provider import summaries, generated artifact
paths, lifecycle evidence paths, and recall summaries. They should remain
generated evidence inside the vault boundary.

## Decision

Add `--report-dir` to `ai-dememory maintenance run`, defaulting to
`reports/maintenance`.

Custom report directories must resolve inside the memory root. The final
rendered maintenance report is secret-scanned before writing. Weekly maintenance
also reuses the guarded consolidation report writer for
`reports/consolidation-dry-run.md`.

## Benefits

- Aligns maintenance reports with the other generated report writers.
- Prevents accidental writes outside the memory root.
- Keeps scheduled maintenance evidence inside the vault boundary.
- Lets acceptance workflows choose a generated maintenance report directory
  without changing canonical memory.

## Limitations

- The report is still generated output and should not be staged as canonical
  memory.
- The guard does not make provider import summaries safe for public sharing.
- The default retention cleanup still targets `reports/maintenance/`.
- Secret scanning can reject a report if future rendered fields contain
  secret-like text.

## Future Risks

- If custom report directories become common, maintenance status may need to
  track the configured directory instead of only `reports/maintenance/`.
- If maintenance reports include longer raw provider excerpts later,
  rendered-output scanning must continue after all sections are assembled.
- If generated index or graph paths become configurable, they may need matching
  in-root guards.

## Dependencies

- ADR 0054 defines maintenance lifecycle artifacts.
- ADR 0123 defines the generated-report boundary for consolidation reports.
- `scripts/maintenance.py` owns maintenance report rendering and writing.
- `scripts/artifact_guard.py` treats `reports/` as generated output.
