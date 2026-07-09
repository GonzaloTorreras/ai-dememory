# ADR 0122: Sleep Plan Report Path Guard

## Status

Accepted.

## Context

`ai-dememory sleep plan` writes generated Markdown and JSON evidence for safe
sleep consolidation candidates. Other v2 generated report writers now validate
custom paths and scan rendered output before writing. Sleep plans still accepted
custom `--output` and `--json-output` paths without that generated-artifact
boundary.

Sleep plans may include excerpts from inbox candidates, conflict summaries,
lifecycle signals, and redacted scan findings. They should remain generated
review evidence and must not become a way to write outside the memory root.

## Decision

Add `--report-path` to the Markdown sleep plan writer and
`--json-report-path` to the JSON sleep plan writer. Keep `--output` and
`--json-output` as compatibility options.

The defaults remain `reports/sleep-plan.md` and `reports/sleep-plan.json`.
Custom paths must resolve inside the memory root. The final rendered Markdown
and JSON text are secret-scanned before writing.

## Benefits

- Aligns sleep plan reports with the other generated report writers.
- Prevents accidental writes outside the memory root.
- Keeps safe sleep consolidation evidence inside the vault boundary.
- Lets review workflows choose generated sleep plan filenames without changing
  canonical memory.

## Limitations

- The reports are still generated output and should not be staged as canonical
  memory.
- The guard does not approve, apply, or promote any sleep candidate.
- The JSON output may still include summaries intended for human review.
- Secret scanning can reject a report if future rendered fields contain
  secret-like text.

## Future Risks

- If sleep reports include longer raw excerpts later, rendered-output scanning
  must continue after all sections are assembled.
- If sleep evidence needs immutable history, the command may need timestamped
  default paths.
- If sleep packets gain configurable output directories, they may need a
  matching inbox-boundary guard.

## Dependencies

- ADR 0004 defines safe sleep consolidation boundaries.
- ADR 0118 defines generated release evidence report path behavior.
- ADR 0121 defines lifecycle report path behavior.
- `scripts/sleep_consolidation.py` owns sleep plan rendering and report writing.
- `scripts/artifact_guard.py` treats `reports/` as generated output.
