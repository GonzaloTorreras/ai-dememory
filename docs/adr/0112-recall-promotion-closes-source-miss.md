# ADR 0112: Recall Promotion Closes Source Miss

## Status

Accepted.

## Context

`ai-dememory recall-fixtures promote-miss` preserved reviewer provenance on a
new fixture, but it left the source file under `inbox/recall-feedback/` with
`status: proposed`. The weekly review plan therefore continued to list an
already-promoted miss as pending. The command also validated fixture shape but
did not prove that the promoted fixture passed the current recall evaluator.

That made release evidence less useful after promotion because reviewers could
not distinguish pending misses from already-reviewed misses, and a bad fixture
could be committed only to fail `eval-recall` later.

## Decision

After a successful promotion, update the source miss frontmatter with:

- `status: promoted`
- `reviewed_by`
- `reviewed_at`
- `promoted_fixture_id`

The recall review planner ignores resolved miss statuses: `promoted`,
`rejected`, and `dismissed`.

Before marking the miss promoted, evaluate the updated fixture file. If the new
fixture does not pass within its configured rank, roll back the fixture file and
leave the source miss in its original proposed state.

Promotion requires the generated search index to exist. Reviewers should run
`ai-dememory index` before promoting a miss.

## Benefits

- Keeps recall review plans focused on unresolved misses.
- Prevents immediately failing fixtures from being committed.
- Preserves a durable link from the source miss to the promoted fixture id.
- Makes release-evidence recall blockers easier to clear after reviewed
  promotion.

## Limitations

- Promotion still does not decide whether a miss is important; that remains a
  reviewer decision.
- The pass check depends on the current generated index and may fail if the
  reviewer has not run `ai-dememory index`.
- Rejected and dismissed miss status remains separate from promotion; ADR 0113
  adds the first-class reviewed outcome command for those states.

## Future Risks

- If search ranking changes, a previously promoted fixture may later fail even
  though it passed at promotion time.
- If fixture suites are split, source miss closure should record the target
  suite as well as the fixture id.
- If review status becomes more formal, resolved miss statuses should move to a
  shared enum used by capture, promotion, and review planning.

## Dependencies

- ADR 0017 defines recall fixture promotion.
- ADR 0045 defines recall fixture review planning.
- ADR 0111 embeds the recall review plan in release evidence.
- ADR 0113 defines rejected and dismissed recall miss review outcomes.
- `scripts/recall_fixtures.py` owns promotion and review-plan behavior.
- `scripts/eval_recall.py` remains the recall pass/fail evaluator.
