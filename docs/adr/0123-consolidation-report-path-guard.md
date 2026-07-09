# ADR 0123: Consolidation Report Path Guard

## Status

Accepted.

## Context

`ai-dememory consolidate --dry-run` writes generated Markdown evidence for
memory review: inbox proposals, duplicate titles and aliases, review-due items,
low-confidence memories, missing durable provenance, disputed memories, and
stale memories. Other v2 generated report writers now validate custom paths and
scan rendered output before writing. The consolidation dry-run still accepted an
arbitrary `--output` path without the same generated-artifact boundary.

Consolidation reports may include memory summaries from public or internal
records. They should remain generated review evidence and must not become a way
to write outside the memory root.

## Decision

Add `--report-path` to `ai-dememory consolidate --dry-run`, while keeping
`--output` as a compatibility option.

The default remains `reports/consolidation-dry-run.md`. Custom paths must
resolve inside the memory root. The final rendered Markdown is secret-scanned
before writing.

## Benefits

- Aligns consolidation reports with the other generated report writers.
- Prevents accidental writes outside the memory root.
- Keeps review evidence inside the vault boundary.
- Lets review workflows choose generated consolidation report filenames without
  changing canonical memory.

## Limitations

- The report is still generated output and should not be staged as canonical
  memory.
- The command remains a dry run; it does not approve, archive, rewrite, or
  promote memory.
- The guard does not make report summaries safe for public sharing.
- Secret scanning can reject a report if future rendered fields contain
  secret-like text.

## Future Risks

- If consolidation reports include longer raw excerpts later, rendered-output
  scanning must continue after all sections are assembled.
- If consolidation evidence needs immutable history, the command may need
  timestamped default paths.
- If generated conflict reports gain the same custom path behavior, they should
  use the same in-root and rendered-output scan boundary.

## Dependencies

- ADR 0001 defines review report and conflict proposal boundaries.
- ADR 0122 defines the same generated-report boundary for sleep plans.
- `scripts/consolidate_memory.py` owns consolidation report rendering and
  writing.
- `scripts/artifact_guard.py` treats `reports/` as generated output.
