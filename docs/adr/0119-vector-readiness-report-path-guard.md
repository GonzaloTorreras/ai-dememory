# ADR 0119: Vector Readiness Report Path Guard

## Status

Accepted.

## Context

`ai-dememory vector status --write-report` writes the generated evidence used
to decide whether a future vector search experiment is justified. Recall review,
manual acceptance, and release evidence report writers now validate custom
report paths and scan rendered Markdown before writing. Vector readiness still
wrote only the default path without that shared generated-report boundary.

Vector readiness reports should remain generated evidence and must not become a
way to write outside the memory root.

## Decision

Add `--report-path` to `ai-dememory vector status --write-report`.

The default remains `reports/vector-readiness.md`. Custom paths must resolve
inside the memory root. The final rendered Markdown is secret-scanned before
writing.

## Benefits

- Aligns vector readiness reports with the other generated report writers.
- Prevents accidental writes outside the memory root.
- Lets local handoff workflows choose a generated report filename without
  changing canonical memory.
- Keeps vector-readiness evidence safe before any future embedding work.

## Limitations

- The report is still generated output and should not be staged as canonical
  memory.
- Path validation does not justify vector search; fixture failures and explicit
  approval are still required.
- Secret scanning can reject a report if future rendered fields contain
  secret-like text.

## Future Risks

- If vector readiness begins rendering full query text or provider details,
  rendered-output scanning must continue after all sections are assembled.
- If vector evidence needs immutable history, this command may need timestamped
  default paths.
- If vector search is later implemented, this report should remain an evidence
  gate rather than a migration command.

## Dependencies

- ADR 0009 defines the measured vector search gate.
- ADR 0115 defines recall review report path behavior.
- ADR 0118 defines release evidence report path behavior.
- `scripts/vector_gate.py` owns vector readiness rendering and report writing.
- `scripts/artifact_guard.py` treats `reports/` as generated output.
