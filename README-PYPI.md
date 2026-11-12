# ai DeMemory

A small, local-first memory for people and AI tools.

This is the V3 alpha, a clean reset. Install the explicitly versioned V3 package
from PyPI; an unpinned stable package install may still select V2.

```bash
python -m pip install "ai-dememory==3.0.0a6"
```

## Portable project wiki

Use ordinary, linked Markdown in each project without a vault, provider or MCP:

```bash
ai-dememory setup --project . --yes
ai-dememory remember "Verify attachments during restore tests." --project . --page lessons.md --title "Restore lessons"
ai-dememory recall "restore attachments" --project .
```

Setup creates a small `docs/dememory/index.md` and adds a managed pointer to
`AGENTS.md`, preserving existing instructions. English templates are optional;
content can remain in its original language. No private memory is imported.
Optional local hooks: add `--with-codex` or `--with-claude` to project setup,
then review/trust the hooks in that client. No MCP server is required.

The dashboard's Project wiki page edits revision-bound pages, inspects sources,
binds read-only shared knowledge and configures local maintenance or separately
consented, budgeted assistance. The fast librarian selects exact excerpts; it
does not invent facts or automatically rewrite knowledge. Markdown remains
usable without DeMemory. See the [wiki guide](https://github.com/GonzaloTorreras/ai-dememory/blob/main/docs/project-wiki.md).

## Private shared vault and existing integrations

```bash
ai-dememory setup
ai-dememory remember "Something worth remembering"
```

The first setup saves a default vault outside the installation, so later
commands work from any directory. A save is reported only after the canonical
Markdown file has been read back successfully. Saving does not build SQLite;
`ai-dememory recall "something"` creates the disposable FTS index lazily. The
default runtime has no daemon, network, model calls, Node dependency or child
processes.

AI integrations are optional. The foreground MCP module exposes seven tools,
including scoped learning with provenance and reversible forgetting. Inference
stays provisional. The optional local workbench manages memory, provider routes,
fallbacks, budgets and consolidation schedules in a browser.

For project-aware Codex integration, run `ai-dememory setup --with-codex --yes`,
then restart Codex and trust UserPromptSubmit and SessionStart in `/hooks`.
Native learning uses the host assistant, not
an additional extraction model. Existing Codex tool approval policy still applies.

## Claude Code user installation

Close Claude Code, run `ai-dememory setup --with-claude --yes`, then restart it. Combine
`--with-claude --with-codex` to install both clients. Setup enables
`harness-claude`, MCP and the local dashboard. It merges the `dememory_v3` MCP
entry into `~/.claude.json` and UserPromptSubmit/SessionStart hooks into
`~/.claude/settings.json`, preserving other settings and hooks. Repeating setup
is a no-op; conflicting entries are refused.

Claude MCP uses explicit **global scope**, so its learning is shared across
projects. Hooks recall by the payload's working directory and fall back to
global memory when there is no project binding. SessionStart provides guidance
on startup/resume/clear/compact. No transcript scan or extra model is involved.

Remove with `ai-dememory serve harness-claude uninstall --user`, then restart
Claude Code. The `<config>/integrations/claude-global.json` receipt identifies
unchanged owned entries; other settings, memories and module settings remain.
Review existing project-local DeMemory connections before enabling user hooks.

## Optional local dashboard

```bash
ai-dememory module enable workbench
ai-dememory serve workbench
```

Open `http://127.0.0.1:8765`. Models and scheduling remain unconfigured/off until
you choose them. On Windows, optional `setup --with-schedule --yes` installs a
current-user hourly check of the saved consolidation schedule (new default:
weekly). No resident worker or conversation ingestion. Pause/change cadence and
scope in the dashboard; remove with `serve workbench --task remove`.
Provider credentials use process-local keys, environment references or the
optional separately authenticated Codex subscription adapter.

V3 is a clean format with no 2.x migration or compatibility layer. Keep secrets
and credentials out of memory. Full source and documentation:
[github.com/GonzaloTorreras/ai-dememory](https://github.com/GonzaloTorreras/ai-dememory).
