# Installation

This repository distributes the `ai-dememory` tool. Personal memory belongs in
a separate private vault, never in this public repository.

**Release scope:** Published stable 2.1.0 is the only package available from
PyPI. TestPyPI prerelease 2.1.1rc2 is the current tagged evaluation route, not
a PyPI stable release. TestPyPI prerelease 2.1.1rc1 remains historical release
evidence rather than a second recommended installation path.

## Published Stable 2.1.0: Legacy First Run

Use `pipx` for normal CLI use: it keeps the Python application isolated while
putting `ai-dememory` on your `PATH`.

```bash
pipx install ai-dememory==2.1.0
ai-dememory init ~/code/my-memory --wizard --require-version 2.1.0
```

This is the shortest truthful wizard-first path for the published package. Its
trailing compatibility gate is legacy 2.1.0 behavior. The exact tagged
[v2.1.0 installation guide](https://github.com/GonzaloTorreras/ai-dememory/blob/v2.1.0/docs/install.md)
keeps the full historical detail. `version-check` is a CI/support diagnostic,
not an installation prerequisite.

`uv` users can replace the first command with
`uv tool install ai-dememory==2.1.0`. On Windows, use a private path such as
`D:\Memory\my-vault`.

## TestPyPI Prerelease 2.1.1rc2: Wizard-First Evaluation

The current reviewed TestPyPI prerelease removes the persistent
`--require-version` pin from new setup and MCP configuration. In an isolated
Python environment, install the exact prerelease and then run the wizard:

```bash
python -m pip install --index-url https://test.pypi.org/simple/ ai-dememory==2.1.1rc2
ai-dememory init ~/code/my-memory --wizard
```

The wizard previews the bounded operational setup, shows its limits and exact
fingerprint, and asks once before it writes `.ai-dememory.toml`. It does not
import chats, create personal memory, install hooks or schedules, or edit a
client configuration. `balanced` is the recommended first-run intensity.

This is an explicit TestPyPI evaluation route, not a PyPI stable upgrade. The
next stable release will provide its own immutable package command.

The earlier 2.1.1rc1 TestPyPI prerelease remains an immutable historical
artifact. New evaluations should use the later rc2 route above, so the wizard
is still the only first-run action presented here.

## Connect An AI Client (Optional)

Connecting Codex, Claude, or another client is deliberately separate: inspect
the generated fragment before copying it into the host configuration.
The wizard stops before this boundary because it cannot safely choose or edit a
host application's configuration on your behalf.

```bash
ai-dememory --root ~/code/my-memory mcp-config --client codex
```

That invocation is the same in 2.1.0 and the TestPyPI prerelease. Stable 2.1.0
then persists the gate inside the generated runtime configuration; the prerelease
omits that generated pin. The generated runtime command contains the bound vault,
a reduced `core` profile, and an idle lease. First-run users do not need to type
those internal arguments themselves.

## Upgrade Or Diagnose

Repair an existing pipx install with the same immutable package pin. Use the
standard `--version` output only when diagnosing a PATH or package issue;
`version-check` remains available for CI and compatibility diagnostics.

```bash
pipx install --force ai-dememory==2.1.0
ai-dememory --version
```

If `pipx` is unavailable, use a virtual environment or see the
[distribution guide](distribution.md). Contributors should use a reviewed local
checkout and the development instructions in `DEVELOPMENT.md`; local/editable
installs are not a normal user path.

## What The Prerelease Wizard Configures

The prerelease interactive wizard changes operational policy only. Personal
values, preferences, recommendations, and project profiles stay in the separate,
optional `onboard` review/apply flow. For automation, the machine-readable
`setup plan --json` preview remains available, but it is not needed before an
interactive first run.

| Intensity | Recall per eligible turn | Scheduled cadence after explicit setup | Provider candidates/run | File/scan ceilings |
| --- | ---: | --- | ---: | --- |
| `minimal` | manual only | weekly | 5 | 32 KiB / 500 entries |
| `balanced` | up to 1,200 tokens | daily + weekly | 20 | 64 KiB / 2,500 entries |
| `active` | up to 2,400 tokens | daily + weekly | 50 | 128 KiB / 10,000 entries |

`active` is a maximum bounded envelope, not an unlimited mode. Host-model
policy is separate: `off` permits deterministic local tools only, `advisory`
lets an already active host agent recommend, and `proposals` lets it create
review-first inbox proposals. ai-dememory makes zero model and embedding calls
in every option.

To create a reusable private GitHub vault template instead of a single vault,
use `ai-dememory vault-template export ~/code/ai-dememory-vault-template` and
follow [Create A Memory Repo](create-memory-repo.md).

## Start Using The Vault

After a successful wizard, no further command is required. The actions below
are optional: choose one only when its stated condition applies.

The wizard is intentionally configuration-only. It does not scan a provider
folder, create durable personal memory, or build an index. When you add
reviewed Markdown that you want to recall, build the disposable local index:

```bash
ai-dememory --root ~/code/my-memory index
```

Run `ai-dememory --root ~/code/my-memory doctor` or
`ai-dememory --root ~/code/my-memory setup health --json` only when you need a
diagnostic; neither is a prerequisite for the first run.

## Advanced Guides (Not Part Of Installation)

These capabilities are deliberately separate from the wizard because they can
connect another application, read optional provider data, start a local server,
or create maintenance automation. Use the focused guide only when you choose
that capability:

- [Local MCP and Docker](local-mcp.md): inspectable client fragments, direct
  server smoke tests, and profiles.
- [MCP client configuration](mcp-client-config.md): Codex, Claude, and generic
  host setup.
- [Local REST API](local-api.md): localhost API and its network-binding
  safeguards.
- [Hook integrations](hooks.md): trust-gated lifecycle hooks.
- [Scheduler and maintenance](scheduler.md): dry runs, provider imports, and
  resource-bounded schedules.
- [Operations runbook](operations.md): diagnostics, maintenance, and upgrade
  procedures for an existing vault.
- [Distribution guide](distribution.md): contributor, package, and release
  procedures. Publishing is intentionally not an installation task.

For repository development, use [DEVELOPMENT.md](../DEVELOPMENT.md) rather than
the end-user installation path.
