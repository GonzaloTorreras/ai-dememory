# ADR 0050: Release Evidence Blockers

Status: Accepted for the v2 draft.

## Context

`ai-dememory release-evidence` reports `release_ready`, automated check rows,
manual acceptance status, and the manual acceptance plan. Consumers still had to
infer why `release_ready` was false by checking dirty worktree state, automated
warnings, automated failures, and manual acceptance arrays separately.

That made PR comments and local handoffs harder to automate because each
consumer needed to duplicate the readiness rule.

## Decision

Add `release_blockers` to release evidence.

The field is a list of structured blocker records. Each record includes:

- `id`: a stable machine-readable blocker id
- `kind`: the blocker category
- `summary`: human-readable explanation
- `count`: number of affected rows or items
- `items`: the relevant paths, checks, or manual acceptance rows

`release_ready` is true only when `release_blockers` is empty. The Markdown
report renders a `Release Blockers` section near the top so humans can see the
same readiness reason before reading detailed evidence.

## Benefits

- Makes strict release-evidence failures directly actionable.
- Gives automation and PR comments a single readiness-failure field to consume.
- Keeps the readiness rule centralized in `scripts/release_evidence.py`.

## Limitations

- The blocker list summarizes local evidence only; it does not query GitHub CI,
  PyPI trusted-publisher settings, or real GUI MCP clients.
- Manual acceptance blockers can be stale if a reviewer records new evidence
  after the report was generated.
- Warnings are treated as blockers because strict release readiness requires no
  warnings.

## Future Risks

- If release checks gain severity levels beyond ok/warn/fail, blocker grouping
  may need to preserve severity separately.
- If external CI state becomes part of release evidence, new external blocker
  kinds should be added rather than overloading automated local blockers.
- If manual acceptance moves outside Markdown records, blocker generation must
  follow the same canonical acceptance backend as the planner.

## Dependencies

- ADR 0033 defines the `release_ready` summary contract.
- ADR 0049 embeds manual acceptance planning in release evidence.
- `scripts/release_check.py` remains the source of automated check rows.
- `scripts/manual_acceptance.py` remains the source of manual acceptance state.
