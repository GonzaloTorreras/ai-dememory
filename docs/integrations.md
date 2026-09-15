# Local harness integrations

The optional `harness` module connects the existing memory core to a client.
It installs project-local MCP settings and one prompt-recall hook. It does not
import transcripts, start a daemon, or select another model. The host assistant
uses its own model to decide when to call the evidenced learning tools.

## Current installation boundary

Installing the package does not connect every project. The current installer
creates a fixed-scope, project-local connection; installing it globally with that
same scope would mix unrelated projects. Global hooks also accumulate with
project hooks, so copying the generated files can cause duplicate recall.
Project-aware global installation is the [next planned slice](roadmap.md#now-one-global-v3-installation-isolated-projects),
not a shipped option. Until it is verified, use the explicit project binding below.
Do not repair V3 by running historical V2 scripts or installing V2 dependencies.

## Try it in an empty project

After installing V3 from source and running `ai-dememory setup`:

```bash
ai-dememory module enable harness
ai-dememory serve harness install --client codex --project <empty-project-path> --scope project:demo
```

For Claude Code, substitute `--client claude`. The installer enables MCP,
records the current Python interpreter and selected vault explicitly, and
refuses to overwrite differing client settings. Existing projects with client
configuration need a reviewed manual merge; automatic config merging is not
implemented. On Windows choose paths without shell metacharacters.

Codex receives `.codex/config.toml` and `.codex/hooks.json`. Claude Code receives
`.mcp.json` and `.claude/settings.json`. These contain local paths: keep them
outside public source control. Open the client in that project and approve its
normal project/MCP trust prompts. In Codex, review the exact command in `/hooks`
and trust that definition before expecting automatic recall. Changed hook
definitions need renewed trust. See the official
[Codex hooks](https://developers.openai.com/codex/hooks) and
[Claude Code hooks](https://code.claude.com/docs/en/hooks) documentation.

## What happens in a conversation

1. `UserPromptSubmit` runs a bounded local keyword lookup in the selected scope
   plus global memory. Very short prompts skip retrieval.
2. Relevant context and concise learning guidance are supplied to the host.
   Prompt text and transcript files are not persisted by this hook.
3. The host may call `memory.learn` for a useful explicit fact or verified
   outcome, including its source. Inferences remain provisional and excluded
   from factual recall. A hook does not guarantee that a model will learn.
4. Another session can retrieve the saved Markdown through `memory.context`.
   Explicit keyed corrections are reversible with `memory.forget`.

There is deliberately no Stop hook or repeated extraction loop. The recall
hook makes no additional model calls. Calls made by the host assistant count
against that host's subscription/API usage, not DeMemory's optional provider
budgets. Configured extraction/consolidation routes are a separate mechanism.

The installed MCP process is bound to the project scope. Cross-scope access is
rejected; reads can include global memory, but global writes require a separate
unbound or appropriately bound connection. The currently unscoped proposal
store is unavailable through a bound connection. This is tool-level isolation,
not a sandbox against another local process with access to the same vault.

## Local acceptance checklist

- In session A, state a synthetic durable fact such as a staging window and ask
  the assistant to remember it. Check the source and scope in the workbench.
- Start a fresh session B and ask for the window without repeating the answer.
  Require a real memory tool result, not the previous conversation context.
- Correct the fact explicitly; confirm the new answer, then undo the correction.
- Bind a second project scope and confirm project-specific memory is absent.
- Ask a trivial arithmetic question; no useful learning should be created.
- Restart the client. Memory survives, while its MCP process exits with the
  client. A failed or malformed recall hook returns empty context, not a block.

Automated protocol tests and generated settings are not proof that every
client/version runs the native hook. Current acceptance and client limitations
are recorded in [development status](development-status.md). Hermes now has the
optional native provider described below; full-client acceptance remains pending.
DSH is DeepSeek Harness and has no native adapter yet. The optional
[sources module](workbench.md#local-conversation-sources) can manually preview
its plain JSONL and local Hermes databases, including live WAL with existing
safe sidecars; that does not install hooks,
watch directories or provide unattended native integration.

## Native Hermes provider (local alpha)

Install the V3 wheel **in the same Python environment that runs Hermes**, then:

```bash
ai-dememory module enable hermes-memory
ai-dememory serve hermes-memory install --home <new-empty-hermes-home> --scope project:demo
```

The command binds the selected DeMemory vault and scope in `dememory.json` and
prepares `config.yaml` in a new, empty Hermes home. It refuses an existing
non-empty profile. It does not install/run Hermes, copy credentials or history,
modify a global client configuration or enable a source schedule. Start Hermes
normally with `HERMES_HOME` pointing to that new home, using its ordinary
authentication flow. Set `AI_DEMEMORY_CONFIG_DIR` too if using an isolated
DeMemory selector; it must match the one where this module was enabled.

The package registers Hermes's `hermes_agent.memory_providers` entry point. There
is no MCP child, HTTP listener, provider API call or separate extraction model
inside this adapter. The host model uses `dememory_context`, `dememory_learn` and
`dememory_forget`; their vault/scope cannot be supplied by model arguments.
Prompt recall uses local FTS (three results / 2,000 characters); explicit context
uses five results / 4,000 characters. A large index rebuild can still be slow;
these are result limits, not wall-clock guarantees. Hermes owns its own workers.

Learning is tied to Hermes's current session and human turn. A short literal
excerpt must occur in the normalized user instruction; skill bodies, bots and
cron/subagent/flush contexts cannot authorize writes. Only content matching the
excerpt can be active; paraphrases/inferences remain provisional. Keyed explicit
corrections and undo use the same core as Codex/Claude MCP. This is evidence
traceability, not a guarantee that a model understands every fact correctly.
Turn provenance includes a fresh lifecycle-binding nonce because Hermes may
reuse turn numbers after resume/rewind. Retries within the live turn are stable;
ordinary restart repeats use content/key deduplication, not a durable event ledger
or a guarantee of exact occurrence idempotency across client restarts.

Full transcripts, native memory mirrors, compression and session-end callbacks
are **not** ingestion paths. Do not also schedule extraction of the same origins
unless intentionally reviewing that separate import. One learning owner per
conversation avoids duplicate extraction and derived-memory feedback.

Hermes external providers are additive by default. The **new isolated profile**
sets `memory.provider: dememory`, `memory.memory_enabled: false` and
`memory.user_profile_enabled: false`, so DeMemory replaces its built-in
MEMORY.md/USER.md stores. Do not disable the `memory` toolset: that also hides
external-provider tools. Hermes still stores its own conversation history.
Existing profiles are never changed automatically. The provider exposes vault
and scope fields to Hermes's memory setup wizard; rebinding requires restart.

Disable `hermes-memory` in DeMemory to stop adapter recall/writes, then restart
Hermes. To restore Hermes's own memory, separately change its provider/flags in
the intended profile; disabling DeMemory does not silently create another writer
or erase the vault. Neither the module nor backup hooks copy a vault into Hermes
backups: back up canonical Markdown and operational state with DeMemory.

Contract checks use the official
[provider interface](https://github.com/NousResearch/hermes-agent/blob/1ad89ac018f26a4f21817ebf37bb09f508656d63/agent/memory_provider.py),
[loader](https://github.com/NousResearch/hermes-agent/blob/1ad89ac018f26a4f21817ebf37bb09f508656d63/plugins/memory/__init__.py)
and [built-in-memory flags](https://github.com/NousResearch/hermes-agent/blob/1ad89ac018f26a4f21817ebf37bb09f508656d63/tests/agent/test_builtin_memory_disabled_surface.py).
Installed entry-point/ABC/normalizer smoke and synthetic cross-adapter episodes
pass; the complete native Hermes loader/manager/model session is **not yet
accepted**. See the current handoff before advertising client support.

## Activity and rollback

`runtime.sqlite` keeps at most 1,000 hook metadata rows: a local occurrence
identifier, scope, recall count, elapsed time and timestamp, not prompt text.
This is separate from the disposable search index. The 3-second hook timeout
is enforced by the host; malformed input and normal operational errors fail open.

To stop recall, run `ai-dememory module disable harness`. To stop future MCP
starts, disable `mcp` too and restart the client. Remove only the generated
DeMemory entries from client configuration; do not delete unrelated settings.
An already-running MCP process must be stopped by its client. Keep the vault
and its operational receipts; uninstalling an integration does not erase memory.
