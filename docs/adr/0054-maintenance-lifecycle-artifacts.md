# ADR 0054: Maintenance Lifecycle Artifacts

Status: Accepted for the v2 draft.

## Context

Daily and weekly maintenance already rebuild the SQLite index, graph cache, and
memory weights. Lifecycle scoring existed as separate CLI commands, and
`memory-weights.json` included lifecycle-derived fields, but scheduled
maintenance did not persist the lifecycle score JSON or review report.

The v2 operating loop expects recurring maintenance to refresh recall quality,
weights, and reviewable performance artifacts without mutating canonical
Markdown memory.

## Decision

Daily and weekly maintenance now refresh:

- `indexes/memory-lifecycle.json`
- `reports/lifecycle.md`

The maintenance result and report include both paths and the number of scored
memories. The artifacts are generated and disposable; canonical memory files are
not rewritten.

Maintenance reports are written under `reports/maintenance/` by default.
`ai-dememory maintenance run --report-dir` can choose another generated report
directory, but the directory must resolve inside the memory root and the final
rendered report is secret-scanned before writing.

## Benefits

- Gives scheduled maintenance a durable explanation for weight changes.
- Makes lifecycle review evidence available without requiring a separate manual
  `lifecycle scores` or `lifecycle report` command after every scheduled run.
- Keeps daily and weekly maintenance aligned with the memory-quality loop.

## Limitations

- Lifecycle scoring still depends on the local generated SQLite index.
- The artifacts are snapshots; they do not replace reviewed promotion,
  conflict, or false-positive workflows.
- Maintenance still imports provider data as inbox candidates only.
- Secret scanning can reject a generated maintenance report if future rendered
  fields contain secret-like text.

## Future Risks

- If lifecycle formulas change, existing generated reports may no longer be
  comparable without a version field.
- If generated artifacts become large, retention policy may need to include
  lifecycle reports separately from maintenance reports.
- If maintenance reports become release artifacts, the timestamped report
  directory should remain explicit in acceptance evidence.

## Dependencies

- ADR 0003 defines lifecycle scoring and outcome feedback.
- ADR 0026 defines opt-in Docker maintenance scheduling.
- `scripts/maintenance.py` remains the scheduled maintenance entry point.
