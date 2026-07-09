# ADR 0187: Recall Review Packet

Status: Accepted

## Context

The remaining v2 recall quality work requires reviewed weekly promotions from
real retrieval misses. Existing commands expose the raw pieces:
`recall-fixtures status`, `recall-fixtures review-plan`,
`recall-fixtures check-miss`, `capture-miss`,
`recall-fixtures promote-miss`, and `recall-fixtures review-miss`.

Those commands are enough for automation and status checks, but the human review
step still needs a practical packet that lists each pending miss with fill-in
fields, reproduction guidance, and the exact promote/reject commands. The
packet must not be mistaken for review evidence or fixture promotion.

## Decision

Add `ai-dememory recall-fixtures packet`.

The command reuses the same `RecallReviewPlan` data as
`recall-fixtures review-plan`. With `--write-report`, it writes
`reports/recall-review-packet.md` by default. The report path must stay inside
the memory root and the rendered packet is secret-scanned before writing.

The packet includes:

- recall freshness and pending/invalid/resolved counts;
- reviewer workflow instructions;
- the candidate check command;
- one reviewer fill-in section per pending miss;
- promote and reject/dismiss command examples;
- invalid and recent resolved summaries;
- final gate reminders for `eval-recall` and `release-evidence --strict`; and
- explicit boundaries that the packet does not promote fixtures or close miss
  files.

`recall-fixtures packet --json` reports whether a file was written and includes:

- `mutates_system=false`;
- `records_fixture_promotions=false`;
- `writes_fixture_file=false`;
- `closes_miss_files=false`; and
- `writes_files`, which is true only when `--write-report` writes the generated
  packet.

Setup planning now lists `recall-fixtures packet --write-report` with the other
generated review artifacts, and package install smoke exercises the command.

## Benefits

- Reviewers get one concrete artifact for weekly recall quality review.
- Pending misses are paired with reproduction and outcome commands.
- The generated packet keeps review guidance separate from reviewed fixture
  promotion.
- Installed package smoke coverage catches missing command wiring.

## Limitations

- The packet does not prove that a miss was reviewed.
- The packet does not update `quality/recall-fixtures.json`.
- ADR 0193 later exposes the same packet renderer as read-only MCP tool
  `memory.recall_review_packet`.
- The packet is overwritten at the configured report path.

## Future Work

- ADR 0212 adds CLI-only timestamped packet archives.
- ADR 0210 adds optional reviewer and PR URL packet metadata.
- ADR 0207 adds offset pagination for pending and malformed recall miss packet
  sections.

## Dependencies

- ADR 0034 defines recall fixture freshness status.
- ADR 0045 defines the recall fixture review plan.
- ADR 0115 defines the generated recall review plan report.
- ADR 0130 defines the candidate miss check.
- ADR 0112 defines promotion of reviewed misses into fixtures.
- ADR 0113 defines rejected and dismissed miss outcomes.
- ADR 0193 defines read-only MCP recall review packet rendering.
- ADR 0207 defines recall review packet pagination.
- ADR 0210 defines optional recall review packet metadata.
- ADR 0212 defines recall review packet archives.
- `scripts/recall_fixtures.py` owns recall review planning, packets,
  promotion, and review outcomes.
