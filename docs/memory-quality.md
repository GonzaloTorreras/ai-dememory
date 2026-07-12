# Memory Quality

Memory quality is measured before retrieval architecture changes. SQLite FTS
remains the default retrieval layer until curated recall fixtures prove it is
insufficient.

## Recall Fixtures

Recall fixtures live in `quality/recall-fixtures.json`.

Each fixture contains:

- `id`: stable fixture id.
- `query`: user-like search query.
- `expected_ids`: memory ids that must be returned.
- `min_rank`: maximum acceptable rank for expected ids.
- `include_sensitive`: whether the fixture may include private/sensitive memory.
- `notes`, `source_ref`, `created_at`: review context.
- `reviewed_by`, `reviewed_at`: provenance for fixtures promoted from reviewed
  misses.

Run:

```bash
ai-dememory eval-recall
ai-dememory recall-fixtures status --json
ai-dememory recall-fixtures review-plan --json
ai-dememory recall-fixtures packet --write-report
```

The command exits nonzero if any expected memory is missing from the configured
rank window.

`recall-fixtures status` reports whether the fixture set is seed-only, stale, or
fresh based on reviewed promotions. Use `--strict` in a weekly review job if you
want missing or old reviewed promotions to fail that job:

```bash
ai-dememory recall-fixtures status --strict --max-age-days 14
```

The status command is advisory for ordinary `release-check` and CI because a
new checkout may not yet have a real retrieval miss to promote. Final release
evidence is stricter: `ai-dememory release-evidence --json` includes
`recall_fixture_freshness`, `recall_fixture_review_plan`, and
`vector_readiness`. `release-evidence --strict` remains blocked with
`recall_fixture_review` until a reviewed promotion makes the fixture set fresh.
If fixture results make a vector experiment eligible, release evidence adds a
`vector_readiness_review` blocker. The reviewed promotion itself is still the
evidence that weekly recall quality is improving from real misses.

For the 2.1.0 release, the five checked-in fixtures are bootstrap fixtures with
`source_ref: initial-quality-fixture`; they validate deterministic mechanics,
not production recall effectiveness. Do not convert their passing result into
a recall-quality claim. Product evidence starts when reviewed misses are
promoted with their source references. A useful next evidence milestone is at
least 20 promoted misses spanning multiple projects and both project-specific
and cross-project queries, reported separately from the bootstrap set.

Use `recall-fixtures review-plan` during weekly review to list pending
`inbox/recall-feedback/` miss files, malformed miss files, fixture freshness,
bounded recent resolved misses, a `candidate_check_command` template, and the
next read-only review actions. The command does not promote misses or write
fixture files.

```bash
ai-dememory recall-fixtures review-plan --resolved-limit 10 --json
ai-dememory recall-fixtures review-plan --write-report
```

`resolved_count` is the total number of promoted, rejected, or dismissed miss
files. `recent_resolved_misses` is a bounded audit sample for handoffs and MCP
clients. Rejected and dismissed misses keep the queue clean but do not satisfy
fixture freshness; only reviewed promotion adds recall-quality evidence.

`--write-report` writes `reports/recall-review-plan.md` as generated review
evidence. The report is useful for manual review and release handoffs, but it
does not promote fixtures, resolve misses, or change canonical memory. Custom
report paths must stay inside the memory root, and the rendered report is
secret-scanned before writing.

Use `recall-fixtures packet --write-report` when a reviewer needs a practical
weekly review handoff:

```bash
ai-dememory recall-fixtures packet --write-report
ai-dememory recall-fixtures packet --write-report --json
ai-dememory recall-fixtures packet --limit 50 --pending-offset 50 --invalid-offset 50 --write-report --json
ai-dememory recall-fixtures packet --reviewer "Reviewer Name" --pr-url https://github.com/... --write-report
ai-dememory recall-fixtures packet --archive --json
```

The packet writes `reports/recall-review-packet.md` by default and includes
fill-in sections for each pending miss, the candidate-check command, promote and
reject/dismiss command examples, and final `eval-recall` and
`release-evidence --strict` reminders. It is generated guidance only: it does
not promote fixtures, close recall misses, or write
`quality/recall-fixtures.json`. Use `--limit`, `--pending-offset`, and
`--invalid-offset` to page high-volume pending and malformed recall miss
sections. Use `--reviewer` and `--pr-url` when a release or PR handoff should
carry reviewer metadata in the packet header. Use `--archive` when the weekly
quality review needs a timestamped generated packet copy under
`reports/recall-review-packets/`. Use
`ai-dememory recall-fixtures packet-archive-status --json` to list generated
packet snapshots with pagination metadata. The status command remains read-only
and does not promote fixtures, close recall misses, or write
`quality/recall-fixtures.json`.

The generated review plan and `release-evidence --json` include the same
candidate-check command template so reviewers can verify rank evidence before
writing a new recall miss.

## Capturing Misses

Check the query first so the review artifact is tied to current search
behavior:

```bash
ai-dememory recall-fixtures check-miss \
  --query "native GitHub connector" \
  --expected-id mem_tool_policy_20260614 \
  --min-rank 5 \
  --json
```

The check is read-only. It reports the expected memory rank, top results,
`candidate_miss`, and the exact `capture-miss` dry-run and write commands to
run next. A candidate still needs human review before it can become fixture
evidence.

Capture reviewed candidates as proposals:

```bash
ai-dememory capture-miss \
  --query "native GitHub connector" \
  --expected-id mem_tool_policy_20260614 \
  --reason "Expected policy memory was absent from the top results." \
  --dry-run

ai-dememory capture-miss \
  --query "native GitHub connector" \
  --expected-id mem_tool_policy_20260614 \
  --reason "Expected policy memory was absent from the top results."
```

Use `--dry-run` first when preparing evidence; it renders the proposed Markdown
without writing files. Miss captures are written to `inbox/recall-feedback/`
only without `--dry-run` and must be reviewed before changing
`quality/recall-fixtures.json`.

After review, promote a miss into the curated fixture set:

```bash
ai-dememory index
ai-dememory recall-fixtures promote-miss \
  --miss inbox/recall-feedback/20260619T120000Z_native-github-connector.md \
  --reviewed-by "Reviewer Name" \
  --notes "Real retrieval miss from weekly review."
```

Promotion verifies the miss file stays under `inbox/recall-feedback/`, checks
that the expected memory id exists, rejects duplicate fixture coverage, records
review provenance, secret-scans the fixture, validates that the fixture passes
against the current generated search index, and then marks the source miss as
`status: promoted` with the promoted fixture id. If the fixture would fail,
promotion rolls back the fixture file and leaves the miss proposed for review.

If review shows that a miss is invalid, obsolete, duplicate, or not useful for
the fixture suite, close it without changing fixtures:

```bash
ai-dememory recall-fixtures review-miss \
  --miss inbox/recall-feedback/20260619T120000Z_native-github-connector.md \
  --status rejected \
  --reviewed-by "Reviewer Name" \
  --reason "Expected memory was obsolete."
```

Use `--status dismissed` when the miss is no longer reproducible or does not
need fixture coverage. The command writes only reviewed frontmatter on the miss
file, secret-scans the review metadata, and keeps canonical memory and
`quality/recall-fixtures.json` unchanged.

## Vector Search Gate

Do not add vector search until recall fixtures show important searches failing
with SQLite FTS and manual review confirms semantic retrieval would help.
The same principle applies to future super-search work from `PLAN.md`: fuzzy
matching, candidate-bundle review, and optional model/provider review must first
prove improvement through reviewed fixtures without increasing leakage.

Run:

```bash
ai-dememory vector status
```

Write a review report:

```bash
ai-dememory vector status --write-report
ai-dememory vector status --write-report --report-path reports/vector-readiness.md
```

The default decision is `not_justified` when all fixtures pass. A vector
experiment is eligible only when recall falls below the configured threshold and
enough fixture cases fail. Custom report paths must stay inside the memory root,
and the rendered Markdown report is secret-scanned before writing.
