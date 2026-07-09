# ADR 0120: Durable Provenance Report Path Guard

## Status

Accepted.

## Context

`ai-dememory provenance --write-report` writes generated evidence for durable
memory review metadata. Release evidence, manual acceptance, recall review, and
vector readiness reports already validate custom report paths and scan rendered
Markdown before writing. Durable provenance still used only the default
`reports/durable-provenance.md` path without the same generated-report
boundary.

Durable provenance reports should stay generated evidence and must not become a
way to write outside the memory root.

## Decision

Add `--report-path` to `ai-dememory provenance --write-report`.

The default remains `reports/durable-provenance.md`. Custom paths must resolve
inside the memory root. The final rendered Markdown is secret-scanned before
writing.

## Benefits

- Aligns durable provenance reports with the other generated report writers.
- Prevents accidental writes outside the memory root.
- Lets release and handoff workflows choose a generated report filename without
  changing canonical memory.
- Keeps durable review evidence safe before publishing v2.

## Limitations

- The report is still generated output and should not be staged as canonical
  memory.
- The audit verifies metadata presence and date shape, not reviewer identity.
- Secret scanning can reject a report if future rendered fields contain
  secret-like text.

## Future Risks

- If durable promotion becomes tool-assisted, this report may need to include
  promotion receipts as well as frontmatter audit results.
- If provenance evidence needs immutable history, this command may need
  timestamped default paths.
- Larger teams may need stronger reviewer identity, signatures, or approval ids.

## Dependencies

- ADR 0015 defines the durable provenance audit contract.
- ADR 0118 defines generated release evidence report path behavior.
- ADR 0119 defines vector readiness report path behavior.
- `scripts/durable_provenance.py` owns durable provenance rendering and report
  writing.
- `scripts/artifact_guard.py` treats `reports/` as generated output.
