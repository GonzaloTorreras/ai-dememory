# ai DeMemory

A small, local-first memory for people and AI tools.

```bash
python -m pip install ai-dememory
ai-dememory setup
ai-dememory remember "Something worth remembering"
```

The first setup saves a default vault outside the installation, so later
commands work from any directory. A save is reported only after the canonical
Markdown file has been read back successfully. Saving does not build SQLite;
`ai-dememory recall "something"` creates the disposable FTS index lazily. The
default runtime has no daemon, network, model calls, Node dependency or child
processes.

AI integrations are optional modules and create review proposals instead of
writing canonical memory. The bundled foreground-only MCP module exposes five
tools when explicitly enabled.

V3 is a clean format with no 2.x migration or compatibility layer. Keep secrets
and credentials out of memory. Full source and documentation:
[github.com/GonzaloTorreras/ai-dememory](https://github.com/GonzaloTorreras/ai-dememory).
