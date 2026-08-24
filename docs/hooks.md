# Local Hook Integrations

`ai-dememory` can inject bounded, relevant reviewed memory at prompt time and
capture small lifecycle-event metadata for review. Hooks are optional. They do
not import chat history, run maintenance, or promote durable memory.

Generated hook commands are vault-bound and include the fail-closed
public-only recall ceiling by default. The `minimal` and `balanced` resource
profiles keep hook metadata capture off; `active` may enable metadata after the
wizard preview. Raw payload capture is always off unless separately requested.
The pending metadata inbox is hard-capped by the selected resource policy
(25/100/500 for minimal/balanced/active), and a full queue suppresses new
captures while preserving deduplication of an existing event.

Every rendered memory section and structured context item preserves its
frontmatter `sensitivity` label. Client or repository policy must enforce the
appropriate egress ceiling. In particular, work on a public repository must
ignore non-public recalled blocks unless the user explicitly authorizes
disclosure and separate review; secret scanning alone cannot classify ordinary
proprietary prose.

For active recall during public-repository work, use an explicit query with
MCP `memory.context` (`public_only=true`, `include_working_memory=false`) or
`memory.search` (`public_only=true`), and fetch an item only with
`memory.get(public_only=true)`. The CLI equivalents are `context "<query>"
--public-only --no-working-memory` and `search "<query>" --public-only`.
Do not use auto context, working-memory tools, graph/resources/prompts, or a
surface without a public-only ceiling for that work.

The CLI supports Codex plugin hooks and Claude Code command hooks. Only
`hooks events` is rootless static metadata. In the unreleased 2.1.2 source
candidate, every stateful `hooks` subcommand, manual `hook-event` capture, and
dispatch resolves an absolute vault in this order: `--root <vault>` (with `~`
expanded), `AI_DEMEMORY_ROOT`, then a local default deliberately saved with
`ai-dememory vault use <absolute-vault-path>`. It never discovers a vault from
the current directory or source checkout. The published 2.1.1 package supports
the first two bindings only until 2.1.2 is released.

```bash
ai-dememory hooks events
ai-dememory hooks list --root ~/code/my-memory
ai-dememory hooks captures --root ~/code/my-memory --json
ai-dememory hooks review --root ~/code/my-memory --help
ai-dememory hooks config --client codex --root ~/code/my-memory
ai-dememory hooks config --client claude --root ~/code/my-memory
```

Use `--root <vault>` for generated hook configuration, automation, or more than
one vault. A saved default is a local interactive convenience, not a portable
replacement for a generated vault-specific fragment:

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
ai-dememory hooks install --client all --root ~/code/my-memory --dry-run --json
ai-dememory hooks uninstall --client all --root ~/code/my-memory --dry-run --json
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
configuration uses the same stdin-JSON/stdout-JSON pattern and calls:

```bash
ai-dememory hook-event dispatch --client claude --event UserPromptSubmit --root ~/code/my-memory
```

Claude Code hook behavior is defined by the official Claude Code hooks
documentation: https://code.claude.com/docs/en/hooks

## JSON Dispatch Contract

Codex, Claude Code, and generic wrappers use the same adapter:

```bash
printf '{"prompt":"continue the scheduler","cwd":"/code/ai-dememory"}' |
  ai-dememory hook-event dispatch --client generic --event UserPromptSubmit --root ~/memory
```

`UserPromptSubmit` extracts `prompt`, `cwd`, and optional `session_id`, builds
turn context, and emits only:

```json
{"hookSpecificOutput":{"hookEventName":"UserPromptSubmit","additionalContext":"..."}}
```

It emits `{}` when recall is irrelevant, the payload is invalid, the index is
missing, or recall fails. `Stop`, `PreCompact`, and `PostCompact` also emit valid
JSON and never print `Captured <path>`. Metadata capture is a separate
best-effort side effect and cannot block the harness.

Native hooks run only after the user trusts the repository and hook command in
the client. Without that trust, use the managed instruction block and memory
recall skill; this fallback is advisory and therefore weaker than a native
hook. Recalled memory is reference data, not trusted instructions.

For recall across repositories, generate the hook with `--root <vault>` or set
`AI_DEMEMORY_ROOT` in the hook environment. The 2.1.2 local default can cover a
generic hook on the same user machine after it was deliberately selected, but a
generated or shared configuration should retain an explicit binding. A plugin
hook with no usable binding returns `{}` and continues without injection; it
never tries the client project or current directory.

## Safety Boundary

When hook metadata has been explicitly enabled, capture stores only:

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

If `.ai-dememory.toml` sets `[learning].session_proposals = true`, `Stop` may
write a deduplicated candidate under `inbox/llm-captures/`. Only structured
learning fields, bullets under an explicit `Learnings`/`Aprendizajes` (or
decision/root-cause) heading, or text inside
`[ai-dememory-learning]...[/ai-dememory-learning]` markers are eligible. The
candidate is secret-scanned, excludes raw transcript content by default, and
remains proposed until human review.

`memory.hook_status` includes a bounded `captures` summary for
`inbox/session-events/`: total count, counts by provider and event, latest
candidate paths, malformed frontmatter count, review status counts,
review-after status counts, bounded due paths, and explicit
`reads_raw_payloads: false` / `writes_files: false` flags. The summary reads
frontmatter only; it does not inspect raw payload bodies. `setup health` adds a
next action when unresolved hook captures are due for review.

Filter high-volume review queues by provider, event, or review status:

```bash
ai-dememory hooks captures --root ~/code/my-memory --provider codex --review-status pending --json
ai-dememory hooks captures --root ~/code/my-memory --provider claude --event SessionStart --write-report
ai-dememory hooks captures --root ~/code/my-memory --created-from 2026-06-01 --created-to 2026-06-30 --json
ai-dememory hooks captures --root ~/code/my-memory --review-after-from 2026-06-20 --review-after-to 2026-06-21 --json
```

Allowed review-status filters are `pending`, `resolved`, `reviewed`,
`rejected`, and `dismissed`. Filtered summaries include `filters` and
`unfiltered_total_count` fields so reviewers can tell scoped results from the
full inbox count. Date-window filters use `YYYY-MM-DD` values and match only
frontmatter `created_at` and `review_after` dates.

Close a reviewed hook capture without promoting memory:

```bash
ai-dememory hooks review --root ~/code/my-memory \
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
ai-dememory hooks archive --root ~/code/my-memory --json
ai-dememory hooks archive --root ~/code/my-memory --provider codex --review-status dismissed --min-reviewed-days 7 --json
```

Apply archival only after reviewing the preview:

```bash
ai-dememory hooks archive --root ~/code/my-memory --apply --min-reviewed-days 7 --json
```

The archive command moves only resolved captures from `inbox/session-events/`
to `archive/session-events/`. It selects candidates from frontmatter only,
does not read raw payload bodies, and does not promote canonical memory.

For a durable review handoff, write a local report:

```bash
ai-dememory hooks captures --root ~/code/my-memory --write-report
ai-dememory hooks captures --root ~/code/my-memory --write-report --report-path reports/hook-captures.md
```

The report path must stay inside the memory root. The rendered report is
secret-scanned before it is written and includes only frontmatter-derived
metadata: counts, due paths, latest candidates, malformed candidates, review
status, providers, events, and fingerprints. It does not include raw hook
payload text even when an individual capture was created with `--capture-raw`.

## Managed Instruction Blocks

`ai-dememory hooks install --root <vault>` patches instruction files with managed blocks:

- Codex: `AGENTS.md`
- Claude Code: `CLAUDE.md`

The managed blocks are bounded by HTML comments and can be updated
idempotently. `ai-dememory hooks uninstall --root <vault>` removes only those blocks and
leaves unrelated instruction text untouched.

The installer does not write client settings files. Use
`ai-dememory hooks config --client <client> --root <vault>` for the hook config fragment and
copy it through the relevant client setup flow.

## Manual Capture

You can test capture without installing hooks:

```bash
printf '{"prompt":"non-secret setup note"}' | ai-dememory hook-event --root ~/code/my-memory --provider codex --event UserPromptSubmit
printf '{"source":"startup"}' | ai-dememory hook-event --root ~/code/my-memory --provider claude --event SessionStart
```

PowerShell:

```powershell
'{"prompt":"non-secret setup note"}' | ai-dememory hook-event --root C:\Users\you\memory --provider codex --event UserPromptSubmit
'{"source":"startup"}' | ai-dememory hook-event --root C:\Users\you\memory --provider claude --event SessionStart
```

Direct capture returns a JSON receipt. Use `hook-event dispatch` to test the
actual harness protocol and prompt-time context injection.

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

Hook capture archival remains CLI-only through `ai-dememory hooks archive --root <vault>`;
reviewers should preview it before running with `--apply`.
