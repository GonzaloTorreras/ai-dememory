# ADR 0204: Review Recommendation Outcome Report

Status: Accepted

## Context

ADR 0191 added accepted/rejected outcome status directly on advisory review
recommendation artifacts. ADR 0196 then added archival for reviewed
recommendations after retention review.

Reviewers still needed an offline sign-off artifact before archival. Listing
recommendations with `--json` is useful for automation, but it is not a durable
Markdown packet that can be reviewed alongside false-positive, conflict, recall,
manual acceptance, and release evidence reports. ADR 0205 exposes the same
report over MCP without writing files.

## Decision

Add a read-only outcome report command:

```bash
ai-dememory review recommendation-outcomes --json
ai-dememory review recommendation-outcomes --outcome-status accepted --json
ai-dememory review recommendation-outcomes --kind conflict --json
ai-dememory review recommendation-outcomes --limit 50 --offset 50 --json
ai-dememory review recommendation-outcomes --limit 50 --invalid-offset 50 --json
```

The command writes `reports/review-recommendation-outcomes.md` by default and
supports `--report-path` for a custom in-vault generated report path. The report
contains:

- selected filters and pagination fields;
- accepted/rejected counts;
- malformed recommendation artifact count;
- reviewed recommendation metadata and outcome rationale;
- side-effect flags proving no review decision was applied and no canonical
  memory was changed; and
- next actions for archival or malformed artifact cleanup.

The report writer uses the existing report path guard and scans the rendered
Markdown for secret-like content before writing.

## Benefits

- Reviewers get a Markdown sign-off packet before archiving reviewed advisory
  recommendations.
- Release handoffs can point to one report instead of requiring ad hoc JSON
  inspection.
- The command follows the same guarded generated-report pattern as
  false-positive and conflict review reports.
- Existing recommendation outcome artifacts remain the source of truth.

## Limitations

- The report is generated evidence, not canonical memory.
- Writing the report does not apply recommendations, suppress findings, resolve
  conflicts, promote memory, or archive artifacts.
- The report covers active recommendation inbox artifacts; archived history is
  still inspected through archive status.
- Outcome reviewer identity remains reviewer-supplied metadata.

## Future Work

ADR 0206 adds offset pagination for large active recommendation outcome queues
and malformed active recommendation artifacts.

## Dependencies

- ADR 0188 defines advisory recommendation artifacts.
- ADR 0191 defines accepted/rejected recommendation outcome status.
- ADR 0196 defines review recommendation archival.
- ADR 0197 defines archive status for reviewed recommendations.
- ADR 0205 exposes read-only MCP outcome report rendering.
- ADR 0206 defines outcome report pagination.
- `scripts/review_memory.py` owns outcome report rendering and path guards.
