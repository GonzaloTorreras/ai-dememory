# Install V3 and start using memory

V3 is an alpha and deliberately does not migrate V2. Keep historical vaults
separate. With Python 3.11 or newer, install the V3 alpha directly from PyPI:

```bash
python -m pip install "ai-dememory==3.0.0a4"
ai-dememory setup
```

The alpha suffix remains intentional; an unpinned stable install can still select
V2. Release wheels and checksums are also available in
[Releases](https://github.com/GonzaloTorreras/ai-dememory/releases). For development
from a checked-out V3 source tree, use `python -m pip install .` instead.

The setup explains the vault location, then offers optional global Codex
integration and, on Windows, scheduled consolidation. Decline both for a purely
manual local vault. Package installation itself does not modify harness settings.

The default vault is saved in your user configuration. You can subsequently run
`ai-dememory status`, `remember`, `recall` and `serve` from any directory; you do
not need to enter the vault. `--vault PATH` is only an intentional override.

After updating an existing installation, reconnect already-running MCP clients
or reopen Codex so they load the new code and tool schema. A running Python
process retains imported modules from its earlier package version. Check the
global CLI with `ai-dememory --version`; reopening the dashboard alone does not
refresh an agent's separate MCP connection.

## Codex and optional scheduled work

```powershell
ai-dememory setup --with-codex --with-schedule --yes
ai-dememory serve workbench
```

`--with-schedule` is Windows-only; omit it on other systems. This reuses an
existing selected vault and preserves configured provider routes and budgets.
Restart Codex and trust the generated UserPromptSubmit and SessionStart hooks in
`/hooks`. The dashboard is at `http://127.0.0.1:8765`; it remains local-only.

No provider login is needed for direct memory tools or recall hooks. A separately
configured provider is only needed for extracting conversation lessons or model
summary proposals. Configure those in the dashboard, not through a long chain
of installation commands. See [the workbench guide](workbench.md).

The optional Windows task checks the consolidation schedule hourly and exits.
New schedules default to weekly/global; choose scope and cadence in the dashboard.
It does not ingest history, wake the PC or run while logged out. Costs, credentials,
task status and removal are explained in [automation](automation.md).

## Verify the basic loop

```bash
ai-dememory remember "A useful fact I explicitly want to keep"
ai-dememory recall "useful fact"
ai-dememory status
```

Manual commands default to global. Add `--scope auto` for the current project.
Saving verifies the Markdown readback; searching lazily builds disposable SQLite.

If status cannot find the vault, inspect the Configuration path it uses, check
an existing `AI_DEMEMORY_CONFIG_DIR` override, and run `ai-dememory setup PATH`
once in the same normal user terminal. Do not create another vault just to work
around a stale selector. `ai-dememory --version` must show V3; use this guide's
commands, not retired V2 wizard/API/source-script instructions.
