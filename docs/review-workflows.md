# Review Workflows

`ai-dememory` keeps review state outside canonical memory. Secret-scan
suppressions and conflict review decisions are stored in
`.ai-dememory-ignore.toml` by default; generated summaries are written under
`reports/`; merge proposals are written under `inbox/conflict-resolution/`.

## Review Modes

Review modes define how much help an LLM may provide during review. They do not
permit automatic durable memory promotion.

New vaults also include explicit review policy defaults in `.ai-dememory.toml`:

```toml
[false_positives]
enabled = true
triage_policy = "human_only"

[conflicts]
enabled = true
scan_on_validate = true
scan_on_consolidate = true
resolution_policy = "human_only"
llm_preselect_min_confidence = 0.85
human_required_severities = ["high", "critical"]
llm_auto_deny_categories = ["restricted", "durable", "policy"]
```

`review modes` and `review plan` include these normalized policy values so
humans and MCP clients can see the active guardrails before doing cleanup. These
fields are guidance in this milestone; they do not grant permission to rewrite
canonical or durable memory.

When `[false_positives].enabled = false`, false-positive review reports and MCP
listing tools return no candidates, and suppress/unignore commands fail without
writing review state. When `[conflicts].enabled = false`, conflict reports and
MCP listing tools return no candidates, and dismiss/keep/merge-proposal commands
fail without writing review state or inbox proposals.

When false-positive, stale false-positive, or conflict Markdown reports are
written, they include a compact `Review Policy` section with the relevant
`enabled` state and policy values from `.ai-dememory.toml`. This lets offline
report reviewers distinguish disabled review from an enabled workflow with no
candidates.

When `[conflicts].scan_on_validate = true`, `ai-dememory validate` runs a
non-blocking conflict scan summary after frontmatter validation succeeds.
When `[conflicts].scan_on_consolidate = true`, `ai-dememory consolidate
--dry-run` includes a non-blocking conflict scan section in the generated
consolidation report.

List modes:

```bash
ai-dememory review modes
```

Configure the active mode:

```bash
ai-dememory review configure-mode --mode assisted --reviewer "Your Name"
```

MCP clients can call `memory.review_configure_mode` for the same local config
write. The receipt includes `canonical_memory_updated=false`; changing review
mode never edits canonical memory.

Generate a task-specific plan:

```bash
ai-dememory review plan --kind conflict
ai-dememory review plan --kind promotion
```

Built-in modes:

- `strict`: human-led review; LLMs may gather evidence but not recommend
  false-positive or conflict outcomes.
- `balanced`: LLMs may group low-risk findings and recommend conflict
  outcomes; humans still accept every suppression, merge, and canonical change.
- `assisted`: LLMs may draft review notes and conflict merge proposals; humans
  still approve suppressions and canonical memory changes.
- `autonomous_proposals`: LLMs may organize or deduplicate low-risk
  public/internal inbox candidates for throughput; durable, restricted, and
  canonical memory changes stay explicit-review only.

Legacy `batch` mode names are accepted as an alias for
`autonomous_proposals`.

## Recommendation Artifacts

LLM-assisted cleanup can store advisory recommendations without applying them:

```bash
ai-dememory review recommendation \
  --kind conflict \
  --target-id conf_... \
  --recommendation keep_memory \
  --rationale "Keep the newer policy after human review." \
  --recommended-by "Local LLM" \
  --confidence 0.72 \
  --evidence mem_policy_new \
  --json
```

Recommendation artifacts are written under `inbox/review-recommendations/`.
They record the active review mode, a policy snapshot, whether the recommended
action is allowed by that mode, and `policy_violation=true` when the
recommendation exceeds the current mode. They always include
`requires_human_approval=true`, `applies_review_decision=false`, and
`writes_canonical_memory=false`.

Use recommendation artifacts as audit evidence only. To accept a recommendation,
a human reviewer must still run the explicit command, such as
`false-positive ignore`, `conflict dismiss`, `conflict resolve --keep`, or
`conflict resolve --merge-proposal`.
Those explicit commands can include `--recommendation-id rec_...` to link the
accepted review state back to the advisory artifact. The link is validated
against the recommendation kind, target id, and expected action before review
state is written.

Inspect pending recommendation artifacts without applying them:

```bash
ai-dememory review recommendations --json
ai-dememory review recommendations --kind conflict --policy-violations-only
ai-dememory review recommendations --outcome-status pending
```

The listing is read-only. It returns counts for pending, policy-violation, and
malformed artifacts, redacts secret-like metadata fields, and includes
`writes_files=false`, `applies_review_decisions=false`, and
`writes_canonical_memory=false`.
`ai-dememory maintenance status`, `ai-dememory setup health --json`, and MCP
`memory.maintenance_status` include a compact `review_recommendations` summary
with pending, accepted, rejected, invalid, policy-violation, and kind counts so
scheduled maintenance can surface stale advisory work without applying it.

Close a recommendation artifact after review without applying it:

```bash
ai-dememory review recommendation-outcome \
  --id rec_... \
  --status accepted \
  --reviewer "Your Name" \
  --reason "Accepted after review." \
  --json
ai-dememory review recommendation-outcomes --json
ai-dememory review recommendation-outcomes --outcome-status accepted --json
ai-dememory review recommendation-outcomes --kind conflict --json
ai-dememory review recommendation-outcomes --limit 50 --offset 50 --json
ai-dememory review recommendation-outcomes --limit 50 --invalid-offset 50 --json
```

Outcome status updates only the selected file under
`inbox/review-recommendations/`. It records reviewer metadata and returns
`outcome_applies_review_decision=false` and
`outcome_writes_canonical_memory=false`. The recommendation-outcomes report is
a generated Markdown sign-off packet under
`reports/review-recommendation-outcomes.md`; it does not apply review
decisions, edit canonical memory, or archive recommendation artifacts. Use
`--limit` and `--offset` to page reviewed recommendation records, and
`--invalid-offset` to page malformed active recommendation artifacts with the
same bounded limit. MCP `memory.review_recommendation_outcome_report` accepts
the same pagination fields and returns the selected page without writing files.

Archive reviewed recommendation artifacts after retention review:

```bash
ai-dememory review recommendations-archive --json
ai-dememory review recommendations-archive --outcome-status accepted --json
ai-dememory review recommendations-archive --min-outcome-days 30 --json
ai-dememory review recommendations-archive --apply --json
ai-dememory review recommendations-archive-status --json
ai-dememory review recommendations-archive-status --recursive --json
ai-dememory review recommendations-archive-status --limit 50 --offset 50 --json
ai-dememory review recommendations-archive-status --limit 50 --invalid-offset 50 --json
ai-dememory review recommendations-archive-restore --id rec_... --json
ai-dememory review recommendations-archive-restore --id rec_... --recursive --json
ai-dememory review recommendations-archive-restore --id rec_... --apply --json
```

The archive command previews by default and only moves accepted or rejected
recommendation artifacts from `inbox/review-recommendations/` to
`archive/review-recommendations/` when `--apply` is supplied. It never applies a
review decision, edits canonical memory, or archives pending recommendations.
The archive-status command is read-only and lists archived recommendation
artifacts with accepted/rejected counts, kind counts, malformed file counts, and
the same side-effect flags. Use `--limit` and `--offset` to page large archive
history, and `--invalid-offset` to page malformed archive artifacts with the
same bounded limit. Use `--recursive` when archived artifacts are grouped under
date or project partitions below `archive/review-recommendations/`. The
archive-restore command previews by default and requires a single archived
recommendation id. With `--apply`, it moves that artifact back to
`inbox/review-recommendations/` only when the destination does not already
exist; it still does not apply review decisions or edit canonical memory. Restore
also accepts `--recursive` to locate a selected artifact inside archive
partitions.

## False Positive Review

Generate the report:

```bash
ai-dememory review false-positives
ai-dememory review false-positives --report-path reports/false-positives.md
ai-dememory review false-positives --due-only
ai-dememory review stale-false-positives
```

Custom report paths must stay inside the memory root. Rendered reports are
secret-scanned before writing.

Each finding gets a deterministic `fp_...` id derived from the redacted
secret-scan finding. Suppress a reviewed false positive:

```bash
ai-dememory false-positive ignore \
  --id fp_... \
  --reason "Reviewed fixture redaction." \
  --reviewer "Your Name" \
  --review-after-days 90 \
  --recommendation-id rec_...
```

If `--review-after-days` is omitted, the command reads
`[false_positives].review_after_days` from `.ai-dememory.toml`. New vaults
default to 90 days. The same section can set `ignore_file` for the shared review
state file used by false-positive suppressions and conflict decisions; new
vaults default it to `.ai-dememory-ignore.toml`. MCP
`memory.false_positive_ignore` uses the same defaults unless the caller supplies
`review_after_days`. CLI and MCP receipts include linked recommendation
metadata when `--recommendation-id` or `recommendation_id` is supplied.
If `[false_positives].enabled = false`, review listing and reports return no
findings even when the secret scanner would detect candidate secrets; ignore and
unignore commands fail before writing `.ai-dememory-ignore.toml`.
JSON and MCP listing responses include `enabled` plus policy metadata so clients
can distinguish disabled review from an enabled workflow with no findings.

Undo the suppression:

```bash
ai-dememory false-positive unignore --id fp_... --reviewer "Your Name"
```

Reasons and reviewer names are secret-scanned before they are written.
Reports derive `review_due` and `review_after_status` from the stored
`review_after` date so expired suppressions can be found during routine review.
Status values are `not_ignored`, `not_scheduled`, `scheduled`, `due`, and
`invalid`; invalid dates are treated as due for review.
Use `--due-only` to write a focused report containing only ignored findings
whose review-after date is due.
Use `review stale-false-positives` to find ignored suppression ids that remain
in `.ai-dememory-ignore.toml` after their current scanner finding disappears.
MCP `memory.false_positive_ignore` returns a structured receipt with the
finding id, reviewer, reviewed date, optional review-after date, and
`review_due`, `review_after_status`, and `canonical_memory_updated=false`.
MCP `memory.false_positive_unignore` records the reviewed removal of that
suppression and returns the same non-canonical mutation receipt shape.

## Conflict Review

Generate the report:

```bash
ai-dememory review conflicts
ai-dememory review conflicts --report-path reports/conflicts.md
```

Custom report paths must stay inside the memory root. Rendered reports are
secret-scanned before writing.

If `--report-path` and `--output` are omitted, conflict reports use
`[conflicts].report_path` from `.ai-dememory.toml`. Conflict merge proposals
use `[conflicts].proposal_path`. New vaults default to
`reports/conflicts.md` and `inbox/conflict-resolution`, and configured paths
must stay inside the vault.
If `[conflicts].enabled = false`, review listing and reports return no
conflicts; dismiss, keep, and merge-proposal commands fail before writing review
state or inbox proposal files.
JSON and MCP listing responses include `enabled` plus policy metadata so clients
can distinguish disabled review from an enabled workflow with no conflicts.
Generated conflict reports include the same compact `Review Policy` section for
offline review evidence.
If `[conflicts].scan_on_validate = true`, `ai-dememory validate` reports the
current conflict count and active conflict count without failing validation.
Validation still fails for malformed memory frontmatter or invalid review
configuration.
If `[conflicts].scan_on_consolidate = true`, `ai-dememory consolidate
--dry-run` includes conflict scan status, counts, and active ids in the
generated report without writing review state or canonical memory.

The scanner flags duplicate title/alias keys and classifies them as:

- `duplicate`
- `preference_conflict`
- `project_decision_conflict`
- `stale_vs_current`
- `tool_policy_conflict`
- `restricted_conflict`

Restricted conflicts take precedence over every other category. A duplicate
active/stale pair is reported as `stale_vs_current` so reviewers can decide
whether to refresh, supersede, or keep the stale memory. Tool memories with
policy markers in tags, title, or aliases are reported as
`tool_policy_conflict` so policy precedence gets an explicit review path before
canonical memory changes.

Dismiss an intentional duplicate:

```bash
ai-dememory conflict dismiss \
  --id conf_... \
  --reason "Intentional cross-reference." \
  --reviewer "Your Name"
```

Record a keep decision without editing memory:

```bash
ai-dememory conflict resolve --id conf_... --keep mem_example --reviewer "Your Name"
```

Write a merge proposal:

```bash
ai-dememory conflict resolve --id conf_... --merge-proposal --reviewer "Your Name"
```

Merge proposals land in `inbox/conflict-resolution/`. A human still has to
promote, supersede, or archive canonical memories manually.
MCP conflict dismiss, keep, and merge-proposal tools return structured receipts
with reviewer metadata, review dates, decisions, and
`canonical_memory_updated=false`. When a recommendation id is supplied, the
stored review state and MCP receipt include `recommendation_id`,
`recommendation_path`, `recommendation_action`, and
`recommendation_policy_violation`.

## MCP Tools

MCP clients can use:

- `memory.review_false_positives`
- `memory.review_stale_false_positives`
- `memory.false_positive_ignore`
- `memory.false_positive_unignore`
- `memory.review_conflicts`
- `memory.conflict_dismiss`
- `memory.conflict_keep`
- `memory.conflict_merge_proposal`
- `memory.review_modes`
- `memory.review_configure_mode`
- `memory.review_plan`
- `memory.review_recommendation`
- `memory.review_recommendations`
- `memory.review_recommendation_archive_status`
- `memory.review_recommendation_archive_restore_preview`
- `memory.review_recommendation_outcome_report`
- `memory.review_recommendation_outcome`

Read tools return structured review candidates. Write tools only update
`.ai-dememory-ignore.toml`, create files under `inbox/conflict-resolution/`,
store advisory recommendation artifacts under `inbox/review-recommendations/`,
record advisory recommendation outcomes, or preview archive restore plans
without moving files.
`memory.review_false_positives` accepts `due_only=true` to return only due
false-positive suppressions plus `returned_count` metadata.
`memory.review_stale_false_positives` returns ignored false-positive
suppressions whose current scanner finding no longer exists.
`memory.review_recommendation_archive_status` lists archived accepted/rejected
recommendation artifacts without moving files. Pass `limit` and `offset` to page
large archive history, pass `invalid_offset` to page malformed archive
artifacts, and pass `recursive=true` to include date or project partitions under
the selected archive root.
`memory.review_recommendation_archive_restore_preview` returns the same
read-only restore plan as `ai-dememory review recommendations-archive-restore
--id <rec_id> --json` without moving files; pass `recursive=true` to search
partitioned archives.
`memory.review_recommendation_outcome_report` renders the reviewed
recommendation outcome sign-off packet without writing `reports/`, applying
review decisions, or mutating canonical memory.
