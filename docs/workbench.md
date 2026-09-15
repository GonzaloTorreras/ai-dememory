# Local workbench

This is an implemented V3 alpha, not a remote administration service. Install
from the V3 source branch and select a vault with `ai-dememory setup` first.

```bash
ai-dememory module enable workbench
ai-dememory serve workbench
```

Open `http://127.0.0.1:8765`. Use `--port 8766` after `workbench` if the default
port is occupied. Ctrl+C stops this service. Only the optional Codex subscription
module starts a bounded child process for explicit login, catalog or generation.

## Memory

Start with scope `global`. Use `project:my-project` for project-only information.
**Current scope** selects an existing scope. **New scope** is a blank text field
with an example placeholder; selecting or applying a scope clears that field.
It is not a second selector and does not copy the current scope.
The management list shows the exact selected scope; retrieval returns that
scope plus global, never another project's records. These labels are routing,
not user authentication or tenant isolation.

Save an explicit statement, optionally with a stable key such as
`preferred-language`. A new explicit statement with that key replaces the old
one in the same scope. Forgetting the latest correction restores its predecessor.
Inactive records remain inspectable; forgetting is not secure erasure.

The extraction panel is for **your own messages**, not an unlabeled transcript
containing assistant replies. Text goes to the selected extractor and may go to
its configured fallback. Up to three supported candidates are admitted per call.
Exact user quotes are active; paraphrases and assistant assertions stay
provisional. This establishes traceability, not universal truth or contradiction
detection. Model-generated keys cannot rewrite existing records.

Core calls with the same stable occurrence reuse the original result. Completed
extraction receipts also preserve original admissions and deduplication aliases
without another provider call. A crash between a Markdown write and receipt
commit remains a recovery limit; these are not one transactional store.

## Providers and routing

Choose **Add provider**, then Codex / ChatGPT subscription, OpenAI API,
Anthropic / Claude API, local, custom, or an enabled provider plugin.
The **profile name (Provider ID)** is your own short alias, such as
`fast-extractor`; routes refer to it. It is not an ID issued by a vendor.
**Load available models** reads the provider's catalog without generating text.
Choose a supported text model or enter its exact ID when discovery is unavailable.
Catalogs may include unsuitable models; discovery is not a generation test.

Named presets fill and hide protocol/endpoint details. Local/custom profiles
expose them under Advanced: Responses uses `/responses`, Messages uses
`/messages`, and OpenAI-compatible uses `/chat/completions`. Enter the API base,
not the final generation URL. OpenAI API uses Responses at
`https://api.openai.com/v1`; Claude uses Messages at
`https://api.anthropic.com/v1`. A local OpenAI-compatible server can use
`http://127.0.0.1:11434/v1`; remote endpoints require HTTPS. The dashboard's
loopback-only listener does not restrict outbound model calls to local servers.

Choose an authentication mode:

- **API key — this workbench session:** paste the key in the password field.
  It is sent only to the local workbench, retained in that process and used for
  the selected endpoint. It is not written to settings, memory, SQLite, browser
  storage or API readback. Closing the tab does not clear it; clearing the key,
  changing the endpoint or restarting the workbench does. Re-enter after restart.
- **API key — environment variable:** enter a name such as `OPENAI_API_KEY` or
  `ANTHROPIC_API_KEY`, not its value. Set it in the environment before starting
  the workbench; use this mode for scheduled work that must survive a restart.
- **No authentication:** for a local or custom service that does not require it.

**Save provider & settings** saves the profile and current route/budget edits.
It does not validate the key against the provider or make a model call. The
table says whether a credential is present, not whether authentication succeeds.
Assign the profile to Extract or Consolidate, choose ordered fallbacks and save.
Session credentials are scoped to this workbench process; another MCP/CLI
process does not inherit them. OS keychain persistence remains future work.

There is no hardcoded model catalog, inferred price or fictional model alias.
Configure reasoning effort only if the selected model supports it;
the Claude adapter currently uses provider-default thinking rather than mapping
OpenAI's reasoning options incorrectly.
Direct API profiles use separate API billing, not a ChatGPT or Claude subscription.
Use the distinct Codex subscription profile for that path.

- `extract`: model that reads a bounded conversation window and proposes facts.
- `consolidate`: independently chosen model for optional summary proposals.
- `hook:codex-stop` or `skill:weekly-review`: named overrides a future/custom
  adapter passes as `route_key`. Adding a route does **not** install that hook.

Saving/retrieving an explicit fact requires no model. “Model for writing memory”
means extraction/admission; the Markdown write itself remains deterministic.
Search remains local FTS without embeddings or model calls.

Fallbacks are ordered profile IDs, for example `cloud` then `local`. Timeouts,
rate limits, server errors, unavailable credentials and malformed responses can
try the next profile. Invalid requests and exhausted application budgets stop.
Keys are resolved independently for each profile and never forwarded to a
fallback. Redirects and environment proxy routing are disabled.

### OAuth and app subscriptions

The optional **codex-subscription** module uses the official Codex AppServer's
managed ChatGPT browser or device-code login. Enable it in the provider form or
Modules, start sign-in, open the official link, then choose **Check sign-in**.
A native `codex` executable is required. Windows checks for `codex.exe` before
generic `codex` on PATH. If neither supplies a native executable, discovery checks
`CODEX_INSTALL_DIR`, the [official standalone installer location](https://learn.chatgpt.com/docs/config-file/environment-variables)
under `%LOCALAPPDATA%\Programs\OpenAI\Codex\bin`, then the observed Desktop layout
under `%LOCALAPPDATA%\OpenAI\Codex\bin\<build>`. The Desktop fallback examines
at most 64 immediate entries and selects the most recently modified executable
(with a deterministic path tie-break), not a verified newest release. It does
not recurse, inspect running processes or run shell wrappers/version probes.
Other layouts can set `AI_DEMEMORY_CODEX_BIN` to the native executable's absolute
path **before starting the workbench**. Wrapper-only installations still need
the native CLI installed; no script launcher is executed.
An explicit override is authoritative: a missing, moved or script path produces
an actionable error, never a silent switch to another executable. Restart the
workbench after installing/updating Codex or changing its path. **Check sign-in**
and login failures show the same guidance and clear stale links/device codes.

This provider login is separate from the Codex memory hook/MCP integration.
Codex can recall and save explicit memories through DeMemory without enabling
this provider; it is only needed when DeMemory itself asks Codex to extract or
summarize text.
The account is isolated in `codex-account` under DeMemory's user config directory,
outside the vault. Codex manages its credential file there; DeMemory does not
copy your existing Codex account or place tokens in vault/UI readback. Disabling
the module cancels pending login but does not erase this saved account.

Catalog and generation use subscription limits and may consume purchased Codex
credits; this is not unlimited or guaranteed free access. After a Codex attempt,
automatic remote API fallback is blocked to avoid switching to separate API
billing. A configured local fallback is allowed. Custom plugins are trusted code
and must document their own billing behavior.

Generation uses an ephemeral, tool-disabled turn with bounded output and deadline.
Incompatible clients fail closed. Pending login expires after ten minutes;
completed requests close and reap the owned child. The route output setting is
not a server-enforced Codex token ceiling. Live authenticated generation remains
a separate acceptance check. See the official
[AppServer contract](https://learn.chatgpt.com/docs/app-server) and
[authentication guide](https://learn.chatgpt.com/docs/auth).

There is no generic OAuth bridge for arbitrary subscriptions. The direct
[OpenAI API](https://developers.openai.com/api/reference/overview#authentication)
supports API keys and workload identity access tokens; this adapter implements
API keys, not workload identity federation. Anthropic directs third-party apps
to API keys or supported cloud providers and does not permit offering Claude.ai
subscription login in another application. See its
[credential policy](https://code.claude.com/docs/en/legal-and-compliance#authentication-and-credential-use).

Your Codex/Claude client can still authenticate using its own supported login
and use the [DeMemory MCP integration](integrations.md). That does not export
its OAuth tokens or turn its subscription into a direct extraction API key.
No login-token scraping or Claude subscription token reuse is implemented.

## Local conversation sources

Enable **sources** in Modules or Local sources. Select one absolute folder and
format, find conversations, and open an inline accordion. Select up to ten with
checkboxes, preview the selection, then extract. Results stay next to each
conversation; a failed batch preserves completed results. Preview expiry or
route changes are checked before the first call. Only user text is retained;
assistant/tool/system output and recognized secret canaries are discarded.
Inspect the scope and extraction route, then explicitly send the preview.
Listing and preview make no model calls. Previews stay in RAM for at most 15
minutes; extraction uses that snapshot, not a file silently reread later.
Changing provider routes requires a new preview. Disabling clears previews.
The scope selector is shared across dashboard pages; you can select an existing
scope or enter a new one. Changing scope clears previews rather than silently
changing an already-approved destination.

For Codex, use **Use Codex sessions folder** or select `$CODEX_HOME/sessions`
(normally `~/.codex/sessions`). The adjacent optional `session_index.jsonl`
supplies titles via `id`/`thread_name`; `session_meta` supplies project/origin.
The filename is secondary technical information, not a conversation name.
This is a bounded local-file adapter, not a promise of stable undocumented file
schemas. Official [AppServer](https://learn.chatgpt.com/docs/app-server) separately
exposes thread names, previews, source kinds, workspace filters and pagination.
No AppServer, account login or model call is started to browse local files.

Codex browsing excludes internal/subagent sessions, including guardian reviews.
Extraction prefers native human-message events; older response-only exports
use filtered fallback. Known bootstrap/review wrappers are excluded. Provenance
that cannot be parsed within the metadata limit is refused, not guessed.

| Format | Current support |
| --- | --- |
| Codex | Titles, workspace, recent-first JSONL; native human events preferred over response mirrors |
| Claude Code | JSONL human messages, excluding tool results |
| Pi | Latest branch ancestry, not all alternative branches concatenated |
| Hermes | One selected root session from local live `state.db` or a checkpointed snapshot; titles/workspace/date use session metadata when available |
| DeepSeek Harness (DSH) | Highest-generation plain JSONL; `.zstd` reported unsupported |
| Generic | User-role JSON/JSONL exports |

Scanning retains up to 100 recent conversations across at most 5,000 directory
entries and depth four, not the first arbitrary 100 files. JSON input is limited
to 2 MB; Codex logs up to 256 MB use only their latest complete 2 MB window and
bounded metadata. Hermes databases and sidecars share a 256 MB limit, with bounded query work.
Previews retain at most 20 user messages / 24,000 characters. Path escapes,
symlinks and junctions are rejected. This is not a full-history importer or
comprehensive PII filter.

For Hermes, select the folder containing `state.db`, not the file itself.
Keep Hermes open when reading its live database: both its existing `-wal` and
`-shm` files must be present, regular and readable. DeMemory uses a short SQLite
read transaction, including committed WAL messages but not pending writer
changes. It does not issue conversation writes, checkpoints or repairs. SQLite
may coordinate transient SHM read marks/locks; live reading does **not** promise
byte-immutable sidecars. No full database copy or extra process is needed.

The database plus sidecars must fit within 256 MB. Lock waits are disabled and
SQL work has a 250 ms progress deadline per connection, not a whole-folder
wall-clock guarantee. An incomplete sidecar pair, busy/inconsistent database,
unsafe path or exhausted query budget is reported as unreadable: retry, or
select a checkpointed snapshot. Live WAL must be on local disk on the same host,
not a LAN mount. Snapshots without sidecars keep the immutable reader and refuse
detected changes during preview.

UNC live paths are rejected; mapped network drives and POSIX network mounts are
not automatically detected. File checks are safeguards against ordinary unsafe
paths, not an adversarial path-swap sandbox.

Hermes previews exclude inactive/summary messages, hidden display rows and
hidden/child sessions when those metadata columns exist. Root-session-only
reading intentionally does not reconstruct compressed or branched lineage;
export that history separately. Titles, workspace paths and conversation IDs
help local browsing, but only the previewed user text reaches the configured
extraction route. This is a source reader, not a native Hermes memory provider.

### Per-harness source schedules

Under **Automate this source**, save the selected folder, format, scope and
interval. Automatic extraction requires its explicit opt-in checkbox; saving
does not immediately call a model. Each rule can run now, pause, resume or be
removed. Rules are independent and use `skill:source-codex`, `skill:source-hermes`,
etc. when configured under Providers; otherwise they inherit Extract. Manual
source extraction uses the same harness-specific route.

While the foreground workbench runs, an enabled rule processes at most one
changed eligible conversation window per interval. Existing provider budgets
and durable extraction receipts apply. Assistant-only activity does not trigger
another model call for the same user window. Unreadable files are counted and
skipped; provider failures stop that run. There is no OS task, extra watcher or
default scan. Disable sources to stop all source rules.

Choose **Recent activity** for the latest bounded windows (the default for all
harnesses), or **Codex history** to read native Codex JSONL from the beginning
and then follow new messages. The history mode:

- Reads complete `event_msg/user_message` events in chronological file order,
  excluding mirrors, internal sessions and synthetic review wrappers. Older
  response-only exports still need manual preview; they are not native history.
- Advances at most one 2 MB window per run, with up to 20 user messages /
  24,000 characters sent to Extract. A daily interval means one window per day;
  **Run now** advances another window without changing the interval.
- Pages beyond the browser's 100-conversation display cap and revisits files
  after each discovery pass. The existing 5,000-entry/four-directory-level scan
  boundary still applies. A displayed limit means choose a smaller dated folder,
  not that the entire archive was imported.
- Waits for the final newline of an in-progress record. Assistant-only windows
  advance without a model call. Oversized user messages, sensitive text and
  malformed lines are counted; an individual record over 2 MB is unsupported.
- Preserves the exact pending byte range across provider failure and restart;
  later appends cannot change that retry. Completed extraction receipts avoid
  another call after a crash before the cursor commit. Common replacement or
  truncation is skipped with a warning; this mode expects append-only native
  logs, not arbitrary in-place rewrites.

Cards show windows/messages inspected, conversations tracked, discovery passes,
remaining bytes for the current file and discard/limit warnings. These are
reading progress, not evidence of memory usefulness or whole-archive completion.

`source-jobs.json` stores at most 16 rules and recent-mode fingerprints (128 per
rule). History cursors live in the existing durable `runtime.sqlite`, separately
from the disposable search index; they contain file hashes/identity and byte
offsets, not raw conversation copies. Back up both with the vault. Removing a
history schedule removes its cursors, not its memories or extraction receipts.
Run a single workbench writer per vault for this alpha. The known Markdown/
admission-receipt crash gap is not made transactional by these cursors.

## Budget and activity

Calls and tokens are daily UTC limits across all operations, including fallback
attempts. USD is optional: zero disables only the currency cap. With a currency
cap, remote profiles require explicit input/output prices per million tokens.
Price accuracy is your responsibility, so this is not a provider invoice limit.
Codex subscription calls count toward local call/token budgets but record zero
API USD; that field does not measure or cap purchased Codex credit consumption.

Every attempt reserves budget before sending; concurrent processes share the
same durable receipt database. Successful reported usage reconciles estimates;
failed or unreported usage retains a conservative reservation. Activity shows
metadata and bounded results, never prompts or raw provider errors. The dashboard
shows recent attempts, not host-wide process/memory telemetry.

## Consolidation

Choose the **Scheduled scope**, enable the schedule, choose hours (24 daily,
168 weekly), and save. There is one saved schedule per vault. It processes only
that scope, independently of the browsing scope above; you can enter a scope
before it has any memories. Settings and cadence persist across restarts, and
missed runs coalesce into one run on resume.

**Run now** names the browsing scope it will process. Running another scope
does not postpone the saved schedule. Running the scheduled scope starts its
next interval, as do changing the scheduled scope or re-enabling the schedule.
Changing only the interval uses the same schedule's prior cadence anchor, not
the most recent run of an unrelated scope. Latest run shows its own scope
separately from the saved scheduled scope.

The current pass examines at most 100 active memories in that scope. It retires
exact duplicate unkeyed records without correction ancestry. Keyed/corrected
records are preserved. With a configured consolidation route, global memory may
also produce at most one shorter, source-linked review proposal. It does not
automatically rewrite summaries or consume pending proposals.
Project-scope cleanup is deterministic and makes no model calls, even when a
global consolidation route is configured. Retired duplicates remain in memory
history; cleanup does not delete their Markdown files.

The foreground server runs due jobs; closing the browser tab is fine. An
[optional Windows task](automation.md) checks consolidation hourly without the
server, while you are logged in. The task does not ingest conversation sources.
The UI distinguishes its installation receipt from live OS status; pause the
saved schedule to stop future consolidation in either runner. Browser-session
keys are unavailable to the task; environment credentials must exist for its
scheduled user. No key is copied into task XML.

There is no resident worker. This alpha runs each foreground job synchronously,
so requests wait during its model calls. Each attempt has a socket
timeout and bounded response/read deadline; multiple fallbacks can take longer.
Use a short fallback chain. Nonblocking progress is a later measured improvement.

## Storage and limits

- `memories/*.md`: canonical records, including provenance and inactive versions.
- `proposals/`: review records, also durable.
- `indexes/memory.sqlite`: disposable search projection.
- `settings.json`: non-secret provider/routing/budget/schedule configuration.
- `runtime.sqlite`: durable budget and metadata receipts; do not delete to rebuild search.
- `jobs.json`: durable last/next-run information; no conversation content.
- `windows-task.json`: optional private OS task ownership receipt, not live telemetry.

Back up durable files with the vault. Local profiles do not by themselves
guarantee that a chosen model server has no telemetry. High-confidence secret
patterns are blocked, but this is not comprehensive PII detection. Remote
memory access, passwords, TLS, API-key scopes and multi-user auth remain in the
[development plan](roadmap.md), not this listener's supported deployment mode.
