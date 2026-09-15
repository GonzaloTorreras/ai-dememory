# ai DeMemory

A small, local-first memory for people and AI tools.

This source describes the unpublished V3 alpha. Install from its V3 checkout
or an explicitly supplied V3 wheel; an unpinned public package install may
still select V2.

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
fallbacks, budgets and foreground consolidation schedules in a browser.

For project-aware Codex integration, enable `harness-codex` and run
`ai-dememory serve harness-codex install --user`, then restart Codex and trust
the generated hook in `/hooks`. Native learning uses the host assistant, not
an additional extraction model. Existing Codex tool approval policy still applies.

```bash
ai-dememory module enable workbench
ai-dememory serve workbench
```

Open `http://127.0.0.1:8765`. Models and scheduling remain unconfigured/off until
you choose them. Provider credentials use environment-variable references.

V3 is a clean format with no 2.x migration or compatibility layer. Keep secrets
and credentials out of memory. Full source and documentation:
[github.com/GonzaloTorreras/ai-dememory](https://github.com/GonzaloTorreras/ai-dememory).
