# Local workbench

This is an implemented V3 alpha, not a remote administration service. Install
from the V3 source branch and select a vault with `ai-dememory setup` first.

```bash
ai-dememory module enable workbench
ai-dememory serve workbench
```

Open `http://127.0.0.1:8765`. Use `--port 8766` after `workbench` if the default
port is occupied. Ctrl+C stops this service; it creates no child processes.

## Memory

Start with scope `global`. Use `project:my-project` for project-only information.
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

Choose **Add provider**, then OpenAI, Anthropic / Claude, local, or custom.
The preset fills the API protocol and base URL; enter your own profile ID and
the exact model ID available to your account. OpenAI uses Responses at
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

No model catalog, inferred prices or fictional model alias is built in. Use the
ID supported by your endpoint. Configure reasoning effort only if it supports it;
the Claude adapter currently uses provider-default thinking rather than mapping
OpenAI's reasoning options incorrectly.
The current adapters do not log into your Codex/ChatGPT subscription and cannot
spend its credits. They use the endpoint's credentials/billing.

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

There is no generic OAuth/subscription login in this configurator. The direct
[OpenAI API](https://developers.openai.com/api/reference/overview#authentication)
supports API keys and workload identity access tokens; this adapter implements
API keys, not workload identity federation. Anthropic directs third-party apps
to API keys or supported cloud providers and does not permit offering Claude.ai
subscription login in another application. See its
[credential policy](https://code.claude.com/docs/en/legal-and-compliance#authentication-and-credential-use).

Your Codex/Claude client can still authenticate using its own supported login
and use the [DeMemory MCP integration](integrations.md). That does not export
its OAuth tokens or turn its subscription into a direct extraction API key.
An OAuth integration will require an officially supported provider flow; no
login-token scraping, placeholder button or automatic token refresh is shipped.

## Budget and activity

Calls and tokens are daily UTC limits across all operations, including fallback
attempts. USD is optional: zero disables only the currency cap. With a currency
cap, remote profiles require explicit input/output prices per million tokens.
Price accuracy is your responsibility, so this is not a provider invoice limit.

Every attempt reserves budget before sending; concurrent processes share the
same durable receipt database. Successful reported usage reconciles estimates;
failed or unreported usage retains a conservative reservation. Activity shows
metadata and bounded results, never prompts or raw provider errors. The dashboard
shows recent attempts, not host-wide process/memory telemetry.

## Consolidation

Enable the schedule, choose hours (24 daily, 168 weekly), and save. Scheduled
runs process global memory; Run now uses the selected Memory scope. The schedule
persists across restarts, and missed runs coalesce into one run on resume.

The current pass examines at most 100 active memories in that scope. It retires
exact duplicate unkeyed records without correction ancestry. Keyed/corrected
records are preserved. With a configured consolidation route, global memory may
also produce at most one shorter, source-linked review proposal. It does not
automatically rewrite summaries or consume pending proposals.

The foreground server must remain running; closing the browser tab is fine.
There is no hidden daemon or OS scheduled task. This alpha runs one job
synchronously, so requests wait during model calls. Each attempt has a socket
timeout and bounded response/read deadline; multiple fallbacks can take longer.
Use a short fallback chain. Nonblocking progress is a later measured improvement.

## Storage and limits

- `memories/*.md`: canonical records, including provenance and inactive versions.
- `proposals/`: review records, also durable.
- `indexes/memory.sqlite`: disposable search projection.
- `settings.json`: non-secret provider/routing/budget/schedule configuration.
- `runtime.sqlite`: durable budget and metadata receipts; do not delete to rebuild search.
- `jobs.json`: durable last/next-run information; no conversation content.

Back up durable files with the vault. Local profiles do not by themselves
guarantee that a chosen model server has no telemetry. High-confidence secret
patterns are blocked, but this is not comprehensive PII detection. Remote
memory access, passwords, TLS, API-key scopes and multi-user auth remain in the
[development plan](roadmap.md), not this listener's supported deployment mode.
