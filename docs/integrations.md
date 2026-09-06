# Local harness integrations

The optional `harness` module connects the existing memory core to a client.
It installs project-local MCP settings and one prompt-recall hook. It does not
import transcripts, start a daemon, or select another model. The host assistant
uses its own model to decide when to call the evidenced learning tools.

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
are recorded in [development status](development-status.md). Hermes and DSH are
not installed adapters yet; DSH still needs an exact product identity.

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
