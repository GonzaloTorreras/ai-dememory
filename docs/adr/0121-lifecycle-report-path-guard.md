# ADR 0121: Lifecycle Report Path Guard

## Status

Accepted.

## Context

`ai-dememory lifecycle report` writes generated Markdown evidence for memory
retrieval and usefulness scores. Other v2 generated report writers now validate
custom paths and scan the rendered Markdown before writing. Lifecycle reports
still accepted an arbitrary output path, which made the generated artifact
boundary weaker than release evidence, recall review, acceptance, vector, and
durable provenance reports.

Lifecycle reports should remain generated evidence and must not become a way to
write outside the memory root.

## Decision

Add `--report-path` to `ai-dememory lifecycle report`, while keeping
`--output` as a compatibility alias.

The default remains `reports/lifecycle.md`. Custom paths must resolve inside the
memory root. The final rendered Markdown is secret-scanned before writing.

## Benefits

- Aligns lifecycle reports with the other generated report writers.
- Prevents accidental writes outside the memory root.
- Keeps daily maintenance lifecycle evidence inside the vault boundary.
- Lets review workflows choose a generated lifecycle report filename without
  changing canonical memory.

## Limitations

- The report is still generated output and should not be staged as canonical
  memory.
- Lifecycle state is still stored in generated SQLite and JSON artifacts.
- Path validation does not make lifecycle scoring canonical or durable.
- Secret scanning can reject a report if future rendered fields contain
  secret-like text.

## Future Risks

- If lifecycle reports include raw queries or outcome notes later, rendered
  output scanning must continue after all sections are assembled.
- If lifecycle evidence needs immutable history, the command may need timestamped
  default paths.
- If lifecycle JSON exports become externally configurable, they may need a
  matching generated-artifact path guard.

## Dependencies

- ADR 0003 defines lifecycle scoring and generated state preservation.
- ADR 0054 defines maintenance lifecycle artifacts.
- ADR 0118 defines generated release evidence report path behavior.
- ADR 0120 defines durable provenance report path behavior.
- `scripts/lifecycle.py` owns lifecycle report rendering and writing.
- `scripts/artifact_guard.py` treats `reports/` as generated output.
