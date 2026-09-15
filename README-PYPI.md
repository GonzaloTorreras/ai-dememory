# ai DeMemory

A small, local-first memory for people and AI tools.

This is the V3 alpha, a clean reset. Use an explicitly versioned V3 artifact
from the [releases page](https://github.com/GonzaloTorreras/ai-dememory/releases)
or its V3 checkout; an unpinned stable package install may still select V2.

```bash
python -m pip install .
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
