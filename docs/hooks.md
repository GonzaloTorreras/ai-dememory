# Local Hook Integrations

`ai-dememory` can capture small lifecycle-event metadata from local LLM tools
into `inbox/session-events/` for review. Hooks are optional. They do not import
chat history, run maintenance, or promote durable memory.

The CLI supports Codex plugin hooks and Claude Code command hooks:

```bash
ai-dememory hooks events
ai-dememory hooks list
ai-dememory hooks captures --json
ai-dememory hooks review --help
ai-dememory hooks config --client codex
ai-dememory hooks config --client claude
```

Use `--root <vault>` when generating config for a vault outside the current
directory:

```bash
ai-dememory hooks config --client codex --root ~/code/my-memory
ai-dememory hooks config --client claude --root ~/code/my-memory
```

Install managed instruction blocks for agents:

```bash
ai-dememory hooks install --client codex --root ~/code/my-memory
ai-dememory hooks install --client claude --root ~/code/my-memory
ai-dememory hooks list --root ~/code/my-memory
```

Remove only the managed block later:

```bash
ai-dememory hooks uninstall --client codex --root ~/code/my-memory
ai-dememory hooks uninstall --client claude --root ~/code/my-memory
```

On Windows PowerShell:

```powershell
ai-dememory hooks config --client codex --root C:\Users\you\memory
ai-dememory hooks config --client claude --root C:\Users\you\memory
ai-dememory hooks install --client codex --root C:\Users\you\memory
ai-dememory hooks install --client claude --root C:\Users\you\memory
```

Use `--dry-run` to preview install or uninstall operations without writing:

```bash
ai-dememory hooks install --client all --dry-run --json
ai-dememory hooks uninstall --client all --dry-run --json
```

## Supported Events

Codex:

- `UserPromptSubmit`
- `PreCompact`
- `PostCompact`
- `Stop`

Claude Code:

- `UserPromptSubmit`
- `SessionStart`
- `PreCompact`
- `Stop`
- `SubagentStop`
- `Notification`

Claude Code command hooks receive JSON context on stdin. The generated
configuration uses the same stdin pattern and calls:

```bash
ai-dememory hook-event --provider claude --event UserPromptSubmit --root ~/code/my-memory
```

Claude Code hook behavior is defined by the official Claude Code hooks
documentation: https://code.claude.com/docs/en/hooks

## Safety Boundary

By default, hook capture stores only:

- provider name
- event name
- SHA-256 payload hash prefix
- review metadata

Raw payloads are not stored unless `--capture-raw` is passed directly to
`ai-dememory hook-event`. Even then, the rendered Markdown is secret-scanned
before writing. Secret-like payloads are rejected and no file is created.

All hook output lands under:

```text
inbox/session-events/
```

Review these files before promoting any information into canonical memory.
Repeated captures with the same provider, event, and payload fingerprint reuse
the existing inbox file instead of writing duplicates.
JSON hook payloads use a canonical sorted-key fingerprint, so formatting-only
or key-order-only changes do not create duplicate inbox files. Non-JSON payloads
use raw-text fingerprints.

`memory.hook_status` includes a bounded `captures` summary for
`inbox/session-events/`: total count, counts by provider and event, latest
candidate paths, malformed frontmatter count, review status counts,
review-after status counts, bounded due paths, and explicit
`reads_raw_payloads: false` / `writes_files: false` flags. The summary reads
frontmatter only; it does not inspect raw payload bodies. `setup health` adds a
next action when unresolved hook captures are due for review.

Filter high-volume review queues by provider, event, or review status:

```bash
ai-dememory hooks captures --provider codex --review-status pending --json
ai-dememory hooks captures --provider claude --event SessionStart --write-report
ai-dememory hooks captures --created-from 2026-06-01 --created-to 2026-06-30 --json
ai-dememory hooks captures --review-after-from 2026-06-20 --review-after-to 2026-06-21 --json
```

Allowed review-status filters are `pending`, `resolved`, `reviewed`,
`rejected`, and `dismissed`. Filtered summaries include `filters` and
`unfiltered_total_count` fields so reviewers can tell scoped results from the
full inbox count. Date-window filters use `YYYY-MM-DD` values and match only
frontmatter `created_at` and `review_after` dates.

Close a reviewed hook capture without promoting memory:

```bash
ai-dememory hooks review \
  --path inbox/session-events/<capture>.md \
  --status dismissed \
  --reviewed-by "Your Name" \
  --reason "No durable memory needed."
```

Allowed statuses are `reviewed`, `rejected`, and `dismissed`. The command
updates only the selected `inbox/session-events/` Markdown file, secret-scans
the receipt metadata before writing, records `reviewed_by` and `reviewed_at`,
and returns `canonical_memory_updated=false`. Resolved captures no longer count
as review-due.

MCP clients can perform the same approval-gated receipt write with
`memory.hook_capture_review`. It accepts the same selected capture path,
review status, reviewer, and reason, stays bounded to `inbox/session-events/`,
and returns `canonical_memory_updated=false`.

Preview archival for reviewed captures:

```bash
ai-dememory hooks archive --json
ai-dememory hooks archive --provider codex --review-status dismissed --min-reviewed-days 7 --json
```

Apply archival only after reviewing the preview:

```bash
ai-dememory hooks archive --apply --min-reviewed-days 7 --json
```

The archive command moves only resolved captures from `inbox/session-events/`
to `archive/session-events/`. It selects candidates from frontmatter only,
does not read raw payload bodies, and does not promote canonical memory.

For a durable review handoff, write a local report:

```bash
ai-dememory hooks captures --write-report
ai-dememory hooks captures --write-report --report-path reports/hook-captures.md
```

The report path must stay inside the memory root. The rendered report is
secret-scanned before it is written and includes only frontmatter-derived
metadata: counts, due paths, latest candidates, malformed candidates, review
status, providers, events, and fingerprints. It does not include raw hook
payload text even when an individual capture was created with `--capture-raw`.

## Managed Instruction Blocks

`ai-dememory hooks install` patches instruction files with managed blocks:

- Codex: `AGENTS.md`
- Claude Code: `CLAUDE.md`

The managed blocks are bounded by HTML comments and can be updated
idempotently. `ai-dememory hooks uninstall` removes only those blocks and
leaves unrelated instruction text untouched.

The installer does not write client settings files. Use
`ai-dememory hooks config --client <client>` for the hook config fragment and
copy it through the relevant client setup flow.

## Manual Capture

You can test capture without installing hooks:

```bash
printf '{"prompt":"non-secret setup note"}' | ai-dememory hook-event --provider codex --event UserPromptSubmit
printf '{"source":"startup"}' | ai-dememory hook-event --provider claude --event SessionStart
```

PowerShell:

```powershell
'{"prompt":"non-secret setup note"}' | ai-dememory hook-event --provider codex --event UserPromptSubmit
'{"source":"startup"}' | ai-dememory hook-event --provider claude --event SessionStart
```

## MCP Helpers

The local MCP server exposes read-only helpers for setup agents:

- `memory.hook_events`
- `memory.hook_config`
- `memory.hook_status`

These tools list supported events, return config fragments, report managed
instruction-block status, and summarize hook capture inbox candidates. They do
not install hooks, modify client settings, or read raw payload bodies.

The MCP server also exposes side-effecting `memory.hook_capture_review` for
reviewers who explicitly approve closing a selected hook capture. It writes
only the review receipt fields on that capture, does not promote canonical
memory, and is not part of the read-only setup helper set.

MCP `memory.hook_status` accepts `capture_provider`, `capture_event`, and
`capture_review_status` arguments for the same frontmatter-only capture
filtering. It also accepts `capture_created_from`, `capture_created_to`,
`capture_review_after_from`, and `capture_review_after_to` date-window
arguments.

Hook capture archival remains CLI-only through `ai-dememory hooks archive`;
reviewers should preview it before running with `--apply`.
