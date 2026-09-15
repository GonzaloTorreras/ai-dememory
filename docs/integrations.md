# Local harness integrations

The optional harness modules connect the existing memory core to a client.
Codex supports user-wide project-aware installation; Claude remains project-local.
Each uses MCP settings and one prompt-recall hook. Neither integration
imports transcripts, starts a daemon, or selects another model. The host assistant
uses its own model to decide when to call the evidenced learning tools.

## Codex: install once for local projects

After installing the V3 package and selecting a vault with `ai-dememory setup`:

```bash
ai-dememory module enable harness-codex
ai-dememory serve harness-codex install --user
```

Restart Codex, open `/hooks` and trust **DeMemory V3: recall this project's memory**.
Trust is per exact definition; it is never bypassed. Package installation alone
does not trust a hook, and no transcript watcher or extra model is enabled.
Existing host tool-approval policy still applies to learning/forgetting; a client
configured to reject all approval requests can recall but may refuse writes.

The installer uses the native Python executable and selected configuration,
adds one owned MCP block to `~/.codex/config.toml` and one UserPromptSubmit hook
to `~/.codex/hooks.json` (`CODEX_HOME` is respected). Other settings are preserved.
Its private receipt is beside the DeMemory selector. Reinstalling is a no-op;
edits to owned definitions cause a conflict instead of silently being overwritten.
Do not copy a fixed-scope project config globally: Codex hooks from different
sources [all run](https://learn.chatgpt.com/docs/hooks).

To replace an existing exact DeMemory-generated project connection, add
`--retire-project <path>` to the user install (repeat for other known projects).
Its explicit scope is retained in the local project mapping; unrelated/edited
project settings are not automatically adopted. The installer does not scan all
repositories. If you already have other project-local DeMemory handlers, retire
them explicitly before using global recall in those projects.

### Project scopes and controls

Native Codex CLI and AppServer were tested with separate MCP processes launched
in each task's directory. Auto mode fixes that scope at startup and binds the
first native caller thread ID; another thread cannot reuse that process. Learning
provenance takes session/turn identity from native transport metadata, not model
guesses. Missing metadata fails with a correlated error, not an unscoped fallback.
This is a local native-client contract, not authentication against another process
owned by the same OS user. Other clients retain explicit scope bindings.

- Explicit folder aliases win; Git worktrees otherwise share their local common
  Git directory. Different clones and same-name folders stay separate.
- Projectless task folders have independent scopes. A bare home/filesystem root
  requires explicit binding; it never silently becomes a global writer.
- Automatic IDs are deterministic from local identity, with no discovery daemon
  or auto-written registry. Rebind a moved project explicitly to retain its scope.
- Reads include genuinely shared `global` memories. Project connections cannot
  write global memory. Use the manual CLI/workbench for intentional global facts.

The existing harness command supports explicit local controls:

```bash
ai-dememory serve harness-codex bind --project <path> --scope project:my-project
ai-dememory serve harness-codex exclude --project <path>
ai-dememory serve harness-codex include --project <path>
```

Exclusion/re-enablement applies to aliases sharing that project scope, including
known worktrees. Already-running auto-scope MCP calls check it again. A changed
scope requires reconnecting the client. These controls do not disable separately
authorized source-ingestion schedules. The existing Modules UI can disable Codex
independently; project alias/exclusion UI is not implemented yet.

`ai-dememory status --json` shows actual runtime/config and resolved project.
Manual save/search support `--scope auto`; their default remains explicit shared
CLI behavior (`global`), not automatic project detection.

### Remove the global connection

```bash
ai-dememory serve harness-codex uninstall --user
```

Restart Codex afterwards. Removal changes only still-owned global entries and
restores unchanged retired project configs. Later user edits are preserved.
Vaults, module settings and project aliases remain. Never remove a vault or run
historical V2 scripts to repair an integration.

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
