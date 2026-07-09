# ADR 0118: Release Evidence Report Path Guard

## Status

Accepted.

## Context

`ai-dememory release-evidence --write-report` writes the main v2 handoff
artifact. Recall review and manual acceptance reports already support explicit
in-root report paths and scan rendered Markdown before writing. Release
evidence still wrote only the default path and did not validate a caller-chosen
report target because there was no caller-chosen target.

As setup planning now advertises generated report commands, release evidence
should use the same generated-artifact boundary as the newer report writers.

## Decision

Add `--report-path` to `ai-dememory release-evidence --write-report`.

The default remains `reports/v2-release-evidence.md`. When a custom path is
provided, it must resolve inside the memory root. The final rendered Markdown is
secret-scanned before writing.

## Benefits

- Aligns release evidence with recall review and manual acceptance report
  writers.
- Prevents accidental writes outside the memory root.
- Lets local handoff workflows choose a generated report filename without
  changing canonical memory.
- Adds a final rendered-output secret scan for the release handoff artifact.

## Limitations

- The report is still generated output and should not be staged as canonical
  memory.
- Path validation does not make release evidence complete; manual acceptance
  and reviewed recall promotion remain separate gates.
- Secret scanning can reject a report if reviewed evidence contains
  secret-like text.

## Future Risks

- If release evidence gains additional user-controlled fields, rendered report
  scanning must continue to happen after all sections are assembled.
- If report output moves outside `reports/`, artifact guard and docs must stay
  aligned.
- If release handoffs need immutable archives, this command may need a
  timestamped default path.

## Dependencies

- ADR 0013 defines the v2 release evidence report.
- ADR 0115 defines recall review report path behavior.
- ADR 0116 defines manual acceptance report path behavior.
- `scripts/release_evidence.py` owns release evidence rendering and report
  writing.
- `scripts/artifact_guard.py` treats `reports/` as generated output.
