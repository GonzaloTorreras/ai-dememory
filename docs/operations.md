# Operations Runbook

This runbook covers normal local operation for the ai-dememory repository.
It follows the unreleased 2.1.0rc1 public source line. Stable 2.0.0 includes the
core local operations but not the wizard, resource intensities, server-enforced
profile upgrades, or generated MCP idle leases.

## Daily Use

From the repository root:

```bash
python3 scripts/ai_dememory.py doctor
python3 scripts/ai_dememory.py setup plan --json
python3 scripts/ai_dememory.py setup health --json
python3 scripts/ai_dememory.py search "topic or project" --limit 5
python3 scripts/ai_dememory.py eval-recall
python3 scripts/ai_dememory.py maintenance status
```

Use `py -3` instead of `python3` on Windows when needed.

`setup plan --json` includes reviewed cron export commands and a
`generated_reports` command group for optional handoff artifacts: recall review
plan, recall review packet, manual acceptance plan, manual acceptance packet,
hook capture review, and release evidence reports. The setup planner itself is
read-only; report files are only written if a reviewer chooses to run those
commands. The separate `generated_archive_status` group lists read-only recall
and manual acceptance packet archive status commands. Packet archive retention
plans are exposed through the separate `generated_archive_retention` group;
they are also read-only previews and do not delete files.

`setup health --json` is also read-only. It combines validation status, context
config status, manual acceptance readiness, recall review status, vector
readiness, scheduler environment/status, provider readiness, maintenance
preflight commands and artifact targets, generated artifact state, generated
packet archive cleanup counts, lock state, and false-positive/conflict review
queues into one local health response.
The response intentionally separates `core_ready`, `retrieval_evaluated`,
`manual_maintenance_ready`, `automation_ready`, `maintenance_ready`,
`integrations_ready`, `autonomy_ready`, and `release_ready`. A seed-only
fixture set is not retrieval evidence: `retrieval_evaluated` requires at least
one valid, fresh reviewed promotion. Manual maintenance readiness does not imply
automation readiness: the latter requires a valid, fresh, host-verified
scheduler receipt. The deprecated `ready` field is scoped to `core_ready` and is
retained only for compatibility.

## Agent And Process Hygiene

Treat model-agent concurrency as a resource budget, not free parallelism.
Repository work defaults to the root agent and at most one bounded, fresh
read-only reviewer. Do not recycle a completed subagent through repeated turns:
some hosts create a complete browser/MCP tool stack per turn and may retain it
after the logical agent disappears.

Generated MCP configs include an idle lease:

- `minimal`: 120 seconds;
- `balanced`: 600 seconds;
- `active`: 1800 seconds.

The Python MCP process exits when the lease expires even if its host keeps the
stdio pipe open. A client may reconnect on the next call. An intentionally
persistent deployment may set `--idle-timeout-seconds 0`, but only when an
external supervisor owns termination and restart.

All package-owned external commands use closed stdin, bounded execution, and
an independently reaped process group/tree. On Windows, each child starts
suspended, is assigned to a retained kill-on-close Job Object, and only then
resumes; cleanup therefore does not depend on a racy PID snapshot or
`taskkill`, and early descendants cannot escape assignment. POSIX uses a
separate session/process group.
MCP smoke reads also have a per-response deadline, so a blocked Git or protocol
child cannot hold the validation process indefinitely.

If a Codex session still shows rising Node/Python process counts after all
subagents finish, stop spawning agents. Confirm parent/child ownership before
terminating only exact completed-agent process trees; never bulk-kill unrelated
Node, Python, browser, shell, or Codex processes.

## Before Indexing Or Exporting

Always run:

```bash
python3 scripts/ai_dememory.py validate
python3 scripts/ai_dememory.py validate --json
python3 scripts/ai_dememory.py secret-scan
```

Then rebuild generated artifacts:

```bash
python3 scripts/ai_dememory.py index
python3 scripts/ai_dememory.py export-context
```

## Weekly Review

1. Inspect `inbox/`, `inbox/llm-captures/`, `inbox/session-events/`, and
   `inbox/recall-feedback/`.
2. Reject and delete any proposal that contains secret-like material.
3. Check fixture freshness with `ai-dememory recall-fixtures status --strict
   --max-age-days 14`.
4. Plan pending miss review with `ai-dememory recall-fixtures review-plan`.
5. Write a generated recall review artifact with `ai-dememory recall-fixtures
   review-plan --write-report` when the review needs file evidence. Report
   paths must stay inside the memory root, and rendered reports are
   secret-scanned before writing.
6. Write a reviewer packet with `ai-dememory recall-fixtures packet
   --write-report` when the review needs fill-in fields and exact
   promote/reject commands. Add `--reviewer` and `--pr-url` when the packet
   should carry release handoff metadata. Add `--archive` to retain a
   timestamped copy under `reports/recall-review-packets/`. The packet is
   generated guidance only. Use `ai-dememory recall-fixtures
   packet-archive-status --json` to list generated packet snapshots without
   promoting fixtures. Use `ai-dememory recall-fixtures
   packet-archive-retention-plan --json` to preview cleanup candidates without
   deleting files.
7. Promote reviewed recall misses with `ai-dememory recall-fixtures
   promote-miss --miss <path> --reviewed-by <name>`.
8. Reject or dismiss invalid misses with `ai-dememory recall-fixtures
   review-miss --miss <path> --status rejected --reviewed-by <name> --reason
   <reason>`.
9. Close hook capture candidates that do not need promotion with
   `ai-dememory hooks review --path <path> --status dismissed --reviewed-by
   <name> --reason <reason>`.
10. Preview archival of resolved hook captures with
   `ai-dememory hooks archive --json`; apply only after review with
   `ai-dememory hooks archive --apply --min-reviewed-days <days> --json`.
11. Promote only reviewed, durable, non-secret memories into `memories/`.
12. Run validation, secret scan, reindex, and consolidation dry-run.

Use `ai-dememory consolidate --dry-run --report-path
reports/consolidation-dry-run.md` when a review packet needs an explicit
consolidation evidence path. The report path must stay inside the memory root.
Use `ai-dememory review false-positives --report-path
reports/false-positives.md` and `ai-dememory review conflicts --report-path
reports/conflicts.md` when attaching review report evidence.
13. Commit reviewed Markdown changes. Generated SQLite, reports, and distilled
   context remain disposable unless explicitly promoted.

## Scheduled Maintenance

Preview scheduler installation before writing OS scheduler state:

```bash
python3 scripts/ai_dememory.py schedule plan --json
python3 scripts/ai_dememory.py schedule plan --intensity minimal --json
python3 scripts/ai_dememory.py schedule setup --dry-run
IMAGE_ID="$(docker image inspect --format '{{.Id}}' ai-dememory:local)"
python3 scripts/ai_dememory.py schedule plan --json --mode docker --image "$IMAGE_ID"
python3 scripts/ai_dememory.py schedule setup --dry-run --mode docker --image "$IMAGE_ID"
python3 scripts/ai_dememory.py schedule cron --json
```

The plan reports the effective `minimal`, `balanced`, or `active` resource
policy, resolved root, exact command, a vault-specific task namespace, and
`plan_sha256`. Install only the exact reviewed projection:

```bash
python3 scripts/ai_dememory.py schedule setup \
  --intensity balanced \
  --expect-plan-sha256 <plan_sha256>
python3 scripts/ai_dememory.py schedule status
```

Installation creates definitions exclusively, reads them back, and records
their exact digests. `schedule status` refreshes verification only on an exact
match and treats cached host verification as stale after five minutes; removal
uses the receipt's original namespace after a vault move, refuses drift, and
compensates partial failure (including exact Windows task XML restoration).
The receipted cadence and intensity remain authoritative for status and full
removal even if resource-policy defaults change later.
`minimal`
installs only weekly maintenance; `balanced` and `active` install daily and
weekly jobs by default. Docker schedules require an immutable image digest, run
without network access, and apply intensity-specific CPU, memory, and PID caps.
The resource policy also bounds provider candidates, bytes per file, scanned
directory entries, report retention, tree-supervised job timeout, and pending
hook captures. Canonical and secret scans, graph pages/nodes/edges, MCP
frames/queues/output, and SQLite audit retention have additional
non-configurable ceilings. Malformed or out-of-range overrides make the policy
invalid instead of widening those ceilings.
Scheduler plan/apply fails closed in that state: it emits the exact
`validation_errors`, creates no definitions or receipt, and rechecks validity
immediately before its first write. Manual and dry-run maintenance reject the
same policy with those diagnostics instead of silently using fallback values.

Run profiles manually:

```bash
python3 scripts/ai_dememory.py maintenance run --profile daily --dry-run --json
python3 scripts/ai_dememory.py maintenance run --profile daily
python3 scripts/ai_dememory.py maintenance run --profile daily --report-dir reports/maintenance
python3 scripts/ai_dememory.py maintenance run --profile weekly
```

The dry-run previews enabled provider imports and generated artifacts without
writing inbox files, indexes, reports, or scheduler state. Daily maintenance
imports enabled providers into `inbox/imports/`, runs secret scan, rebuilds the
index, refreshes the graph cache, recalculates weights, refreshes lifecycle
score artifacts, and writes a report. Weekly maintenance also writes the
consolidation dry-run report, writes `reports/sleep-plan.md`, writes
`reports/hook-captures.md`, runs recall fixtures, and cleans old maintenance
reports.
Custom maintenance report directories must stay inside the memory root, and
rendered maintenance reports are secret-scanned before writing.
Use `ai-dememory sleep plan --report-path reports/sleep-plan.md` and
`ai-dememory sleep plan --json --json-report-path reports/sleep-plan.json`
when review packets need explicit sleep plan evidence paths. The weekly
maintenance profile writes the default Markdown sleep plan report automatically
as generated review evidence; it does not write sleep review packets or mutate
canonical memory.
Use `ai-dememory sleep --dry-run --json` when a scheduler, plugin, or MCP
client needs a no-write preview, and `ai-dememory sleep --propose --json` when
review packets should be written under `inbox/sleep-consolidation/` without
editing canonical memory.
Use `ai-dememory sleep --apply-reviewed --id <sleep_id> --json` when following
the roadmap alias for the same reviewed packet writer.

`maintenance status` reports recent maintenance reports, generated artifact
state and freshness for the index, graph, weights, lifecycle scores, lifecycle
report, and hook capture report, generated packet archive cleanup counts,
false-positive review due counts, stale suppression counts, conflict review
counts, hook capture review counts, and sleep plan report status. It does not
refresh artifacts or delete generated packet archives.
It also reports the resolved resource policy and explicitly states zero
ai-dememory runtime model calls and embedding calls per maintenance run. Any
tokens consumed by an already active host agent under `advisory` or
`proposals` policy remain host usage.
Use `ai-dememory lifecycle report --report-path reports/lifecycle.md` when a
review packet needs an explicit lifecycle report path; the path must stay inside
the memory root.

## Provider Imports

Configure providers explicitly:

```bash
python3 scripts/ai_dememory.py providers detect
python3 scripts/ai_dememory.py setup plan --json
python3 scripts/ai_dememory.py setup health --json
python3 scripts/ai_dememory.py providers plan --json
python3 scripts/ai_dememory.py providers configure codex --path "$HOME/.codex" --dry-run --json
python3 scripts/ai_dememory.py providers configure codex --path "$HOME/.codex"
python3 scripts/ai_dememory.py import-chats codex
```

Imported chats are review candidates. They must be scanned and rewritten before
promotion into canonical memory. Preview provider configuration before writing
`.ai-dememory.toml`; the configure dry-run normalizes the selected path and
reports whether it exists without reading provider files.

## Monthly Review

1. Review durable memories whose `review_after` date is due.
2. Check low-confidence or stale memories from the consolidation dry-run report.
3. Review retrieval misses from usage notes, `retrieval_log`, or
   `inbox/recall-feedback/`.
4. Decide whether FTS recall is good enough; do not add vector search until
   measured misses justify it.

## Release Validation

Before marking v2.0 ready for review, run the static checks:

```bash
python3 scripts/ai_dememory.py doctor
python3 scripts/ai_dememory.py verify-mcp
python3 scripts/ai_dememory.py release-check
python3 scripts/ai_dememory.py release-evidence --json
python3 scripts/ai_dememory.py release-evidence --write-report --report-path reports/v2-release-evidence.md
python3 scripts/ai_dememory.py acceptance status --json
python3 scripts/ai_dememory.py acceptance plan --json
python3 scripts/ai_dememory.py acceptance plan --write-report
python3 scripts/ai_dememory.py acceptance packet --write-report
python3 scripts/ai_dememory.py acceptance packet --limit 50 --offset 50 --write-report
python3 scripts/ai_dememory.py acceptance verify --json
python3 scripts/ai_dememory.py provenance --json
python3 scripts/ai_dememory.py provenance --write-report --report-path reports/durable-provenance.md
python3 scripts/ai_dememory.py validate
python3 scripts/ai_dememory.py secret-scan
python3 scripts/ai_dememory.py eval-recall
python3 scripts/ai_dememory.py recall-fixtures status --json
python3 scripts/ai_dememory.py recall-fixtures review-plan --write-report
python3 scripts/ai_dememory.py recall-fixtures packet --write-report
python3 scripts/ai_dememory.py recall-fixtures promote-miss --help
python3 scripts/ai_dememory.py recall-fixtures review-miss --help
python3 -m unittest discover -s tests -t .
python3 -m compileall -q scripts mcp/server ai_dememory_tool
```

`release-evidence --json` includes `manual_acceptance_plan` so the handoff can
show the remaining manual checks, blocked items, and reviewed evidence commands
without running a second planner command. Each incomplete plan item includes
`suggested_artifacts` describing the proof to attach, such as MCP client logs,
reviewed inbox paths, generated maintenance reports, or TestPyPI workflow URLs.
`acceptance plan --write-report` writes that manual acceptance plan to
`reports/manual-acceptance-plan.md` for review packets without recording
evidence.
`acceptance packet --write-report` writes
`reports/manual-acceptance-packet.md`, which gives reviewers fill-in sections,
suggested artifacts, and pass/block record commands for each incomplete manual
acceptance item. Use `--limit` and `--offset` to page large incomplete-item
sections. Use `--reviewer` and `--pr-url` to pre-fill packet handoff metadata.
Use `--archive` to retain a timestamped generated copy under
`reports/manual-acceptance-packets/`. It is generated guidance only and does
not record evidence. Use `acceptance packet-archive-status --json` to list
generated packet snapshots with `limit` and `offset`; the status command is
read-only and does not record evidence. Use
`acceptance packet-archive-retention-plan --json` to preview cleanup
candidates without deleting files.
It also includes `release_blockers`, which is the machine-readable list of
dirty worktree, automated check, recall fixture, vector readiness, and manual
acceptance issues that currently prevent `release_ready`. The embedded
`vector_readiness` object reuses the measured recall gate, remains read-only,
and reports `creates_embeddings=false`.
The embedded `setup_health_summary` mirrors the passive setup-health surface in
a compact form so the same handoff shows scheduler readiness, hook capture
review due counts, provider import readiness, recall review, vector readiness,
validation, context defaults, and next actions without running maintenance or
installing hooks or schedules.

After the draft PR exists, set `AI_DEMEMORY_PR_URL` and run the stricter
release and runtime checks:

```bash
AI_DEMEMORY_PR_URL="https://github.com/GonzaloTorreras/ai-dememory/pull/<number>" python3 scripts/ai_dememory.py release-check --strict
AI_DEMEMORY_PR_URL="https://github.com/GonzaloTorreras/ai-dememory/pull/<number>" python3 scripts/ai_dememory.py mcp-smoke
```

Confirm `mcp-smoke` includes `OK notifications/initialized` and `OK ping`,
matches JSON-RPC responses by id, follows paginated MCP list methods, rejects
sensitive resources by default, and keeps write-capable tools under their
intended inbox directories. The
fixture smoke also exercises recall misses, lifecycle feedback, provider import,
maintenance status, scheduler plans, hook config, sleep consolidation, and
review workflow tools.

## Failure Handling

- `secret-scan` fails: do not index or export. Remove the offending content from
  versioned memory and keep any real secret outside the repo for human review.
- `validate` fails: fix frontmatter before indexing.
- `index` fails: fix scanner/schema failures first; the SQLite database is
  generated and can be deleted/rebuilt.
- `doctor` warns that the index is missing: run `ai-dememory index`. Fresh
  vaults skip distribution-only MCP contract checks. Use `ai-dememory doctor
  --json --summary` to see the selected `vault`, `distribution`, or `unknown`
  profile.
- MCP client cannot start: verify the installed `ai-dememory` command is on
  `PATH` and set `AI_DEMEMORY_ROOT` to the explicit private vault. A source-
  development launch may use the repository as `cwd`, but never as the vault.
- MCP runtime smoke refuses to run: create the PR first and set
  `AI_DEMEMORY_PR_URL` to the draft PR URL.
- Scheduler install fails: run `ai-dememory schedule setup --dry-run`, inspect
  `resource_policy_valid`/`validation_errors` from `ai-dememory schedule plan
  --json`, then fix the policy or platform scheduler. Never install the emitted
  host command manually while the resource policy is invalid.

## Safety Invariants

- No durable memory mutation without human review.
- No secrets in Markdown, reports, indexes, distilled context, or inbox captures.
- No merge without the strict CI, fresh exact-head `READY` review, tuple-bound
  receipt, and other standing-delegation conditions in `AGENTS.md`. No release
  tag, trusted-publishing dispatch, or package publication without separate,
  explicit owner authorization for the exact tag and commit. A reviewed merge,
  including a release-preparation merge, never implies either authorization.
- MCP write paths stay proposal-only unless a human explicitly approves a
  different workflow.
- Package and plugin installation do not create background jobs. Scheduler,
  provider import, and hook capture are opt-in.
