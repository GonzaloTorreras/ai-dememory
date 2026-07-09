# ADR 0126: Recall Review Report Secret Scan

## Status

Accepted.

## Context

`ai-dememory recall-fixtures review-plan --write-report` writes a generated
Markdown report under `reports/recall-review-plan.md`. The writer already
rejects report paths outside the memory root, and recall miss fields are
redacted when individual frontmatter values look secret-like.

Other generated v2 report writers also scan the fully rendered Markdown before
writing. The recall review report did not have that final rendered-output scan,
which made it weaker than release evidence, manual acceptance, vector,
provenance, lifecycle, sleep, consolidation, review, and maintenance reports.

## Decision

Scan the rendered recall review report before writing it. If the scanner finds
secret-like content, reject the report with `recall review report rejected by
secret scan` and leave the target file unwritten.

The report remains generated evidence only. It still does not promote recall
fixtures, reject misses, dismiss misses, or edit canonical memory.

## Benefits

- Aligns recall review reports with the generated-report security boundary.
- Catches future unredacted fields added after per-field redaction.
- Prevents accidental generated report writes when rendered output is unsafe.
- Keeps manual release handoff artifacts safer to inspect and attach.

## Limitations

- Secret scanning is heuristic and can still miss novel secret formats.
- A rejected report does not fix the underlying recall miss; reviewers must
  inspect or remove the unsafe source file.
- The scanner may reject a report because of a false positive in generated
  text.

## Future Risks

- If recall review reports add raw context snippets, the final scan must remain
  after all sections are rendered.
- If reports become timestamped artifacts, every output path must keep the same
  rendered scan.
- If resolved recall miss history grows large, secret scanning may need
  streaming or pagination to avoid slow review-plan runs.

## Dependencies

- ADR 0115 defines recall review plan reports.
- ADR 0118 through ADR 0125 define the broader generated-report path and secret
  scan boundary.
- `scripts/recall_fixtures.py` owns recall review report rendering and writing.
