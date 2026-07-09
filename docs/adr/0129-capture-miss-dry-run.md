# ADR 0129: Capture Miss Dry Run

## Status

Accepted.

## Context

Release evidence blocks v2 readiness until a reviewer promotes a real recall
miss into `quality/recall-fixtures.json`. When no pending miss files exist, the
next action is to capture one under `inbox/recall-feedback/`.

`ai-dememory capture-miss` was write-only. That made it harder for reviewers to
prepare and inspect the exact Markdown that would be written before creating an
inbox artifact. Manual acceptance already has read-only templates; recall-miss
capture needed the same review-first affordance.

## Decision

Add `--dry-run` to `ai-dememory capture-miss`.

Dry run mode:

- validates the query, reason, and expected target;
- runs the same field and rendered-output secret scans as the write path;
- prints the proposed recall-miss Markdown;
- supports `--json` with `writes_files: false`;
- does not create `inbox/recall-feedback/` or write any files.

The normal write path still writes only under `inbox/recall-feedback/` and now
supports `--json` with `writes_files: true` and the written relative path.

## Benefits

- Lets reviewers preview recall-miss evidence before writing inbox files.
- Makes the release-evidence recall blocker easier to act on without weakening
  the requirement for a real reviewed miss.
- Keeps secret scanning identical between preview and write paths.
- Gives automation a machine-readable way to assert whether files were written.

## Limitations

- Dry run output is not evidence by itself and does not satisfy recall fixture
  freshness.
- The command does not verify that a search actually missed; reviewers still
  need to inspect real retrieval behavior.
- The rendered preview can contain non-secret but sensitive context if the user
  supplies it.

## Future Risks

- If recall-miss frontmatter gains new fields, dry run and write rendering must
  remain shared.
- If GUI clients expose dry run previews, they should avoid storing rendered
  text in logs by default.
- If release evidence later links to pending miss previews, it must still
  require a written, reviewed miss before fixture promotion.

## Dependencies

- ADR 0017 defines reviewed recall miss promotion.
- ADR 0110 defines recall freshness as a release blocker.
- ADR 0111 embeds recall review planning in release evidence.
- `scripts/capture_miss.py` owns recall miss rendering and writing.
- `scripts/recall_fixtures.py` owns reviewed promotion into fixtures.
