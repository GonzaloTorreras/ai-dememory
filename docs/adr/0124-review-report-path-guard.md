# ADR 0124: Review Report Path Guard

## Status

Accepted.

## Context

`ai-dememory review false-positives` and `ai-dememory review conflicts` write
generated Markdown evidence for review workflows. Other v2 generated report
writers now validate custom paths and scan rendered output before writing. The
review reports still accepted arbitrary `--output` paths without the same
generated-artifact boundary.

False-positive reports contain redacted secret-scan findings. Conflict reports
contain memory ids, paths, overlap keys, and public/internal summaries. They
should remain generated review evidence and must not become a way to write
outside the memory root.

## Decision

Add `--report-path` to both review report commands, while keeping `--output` as
a compatibility option.

The defaults remain `reports/false-positives.md` and `reports/conflicts.md`.
Custom paths must resolve inside the memory root. The final rendered Markdown is
secret-scanned before writing.

## Benefits

- Aligns review reports with the other generated report writers.
- Prevents accidental writes outside the memory root.
- Keeps false-positive and conflict review evidence inside the vault boundary.
- Lets review workflows choose generated report filenames without changing
  canonical memory.

## Limitations

- The reports are still generated output and should not be staged as canonical
  memory.
- The guard does not decide whether a finding is a false positive.
- The guard does not resolve conflicts or promote merge proposals.
- Secret scanning can reject a report if future rendered fields contain
  secret-like text.

## Future Risks

- If review reports include longer raw excerpts later, rendered-output scanning
  must continue after all sections are assembled.
- If review evidence needs immutable history, the commands may need timestamped
  default paths.
- If MCP review report tools later support writing reports, they should reuse
  the same path boundary.

## Dependencies

- ADR 0001 defines review report and conflict proposal boundaries.
- ADR 0123 defines the same generated-report boundary for consolidation reports.
- `scripts/review_memory.py` owns false-positive and conflict report rendering
  and writing.
- `scripts/artifact_guard.py` treats `reports/` as generated output.
