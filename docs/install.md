# Installation

This repository distributes the `ai-dememory` tool. Personal memory belongs in
a separate private vault, never in this public repository.

**Release scope:** ai-dememory 2.1.1 is the current stable PyPI release.
Source candidate: 2.1.2, unreleased; it is not installable from a package index
until it is tagged and published.

## Install And Run The Wizard

Use `pipx` for normal CLI use: it keeps the Python application isolated while
putting `ai-dememory` on your `PATH`.

```bash
pipx install ai-dememory
ai-dememory init ~/code/my-memory --wizard
```

This is the shortest first-run path for the stable package.

`uv` users can replace the first command with
`uv tool install ai-dememory`. On Windows, use a private path such as
`D:\Memory\my-vault`.

The wizard previews the bounded operational setup, shows its limits and exact
fingerprint, and asks once before it writes `.ai-dememory.toml`. It does not
import chats, create personal memory, install hooks or schedules, or edit a
client configuration. `balanced` is the recommended first-run intensity.

The upcoming 2.1.2 correction then offers to remember the selected vault as
this machine's local default. That is explicit opt-in and stores only the
absolute path in per-user configuration outside the vault; it does not store,
inspect, or move memory. `--root` and `AI_DEMEMORY_ROOT` remain available for
another vault. Managing an existing default belongs in the
[operations runbook](operations.md), not in first-run setup.

The wizard is the only required first-run command after installation.

Manual edits are not required. If you maintain an existing customized vault,
the 2.1.2 candidate validates real TOML, known fields, and exact types before
the wizard writes anything. See [Vault Configuration](configuration.md) for the
contract and the short migration checklist.

## Connect An AI Client (Optional)

Connecting Codex, Claude, or another client is deliberately separate: inspect
the generated fragment before copying it into the host configuration.
The wizard stops before this boundary because it cannot safely choose or edit a
host application's configuration on your behalf.

```bash
ai-dememory --root ~/code/my-memory mcp-config --client codex
```

The generated runtime command contains the bound vault, a reduced `core`
profile, and an idle lease. First-run users do not need to hand-assemble its
internal runtime arguments.

## Upgrade Or Diagnose

Repair an existing pipx install with the current stable package. Use the
standard `--version` output only when diagnosing a PATH or package issue.

```bash
pipx install --force ai-dememory
ai-dememory --version
```

If `pipx` is unavailable, use a virtual environment or see the
[distribution guide](distribution.md). Contributors should use a reviewed local
checkout and the development instructions in `DEVELOPMENT.md`; local/editable
installs are not a normal user path.

## What The Published Wizard Configures

The interactive wizard changes operational policy only. Personal values,
preferences, recommendations, and project profiles stay in the separate,
optional `onboard` review/apply flow. For automation, the machine-readable
`setup plan --json` preview remains available, but it is not needed before an
interactive first run.

| Intensity | Recall per eligible turn | Potential cadence if you later install it | Provider candidates/run | File/scan ceilings |
| --- | ---: | --- | ---: | --- |
| `minimal` | manual only | weekly | 5 | 32 KiB / 500 entries |
| `balanced` | up to 1,200 tokens | daily + weekly | 20 | 64 KiB / 2,500 entries |
| `active` | up to 2,400 tokens | daily + weekly | 50 | 128 KiB / 10,000 entries |

`active` is a maximum bounded envelope, not an unlimited mode. The table is a
policy preview: the wizard leaves scheduling disabled, so no cadence begins
until you separately review and install one. Host-AI policy is also separate:
`off` permits deterministic local tools only, `advisory` lets an already active
host agent recommend, and `proposals` lets it draft review-first inbox
proposals. ai-dememory makes zero model and embedding calls in every option;
any model consumption belongs to an agent you separately run, not to the
wizard.

## Optional Personal Baseline (`onboard`)

The operational wizard deliberately does not collect personal values,
preferences, recommendations, or project profiles. If you choose to create a
reviewed durable baseline later, use the separate interactive preview:

```bash
ai-dememory --root ~/code/my-memory onboard
```

It explains every field, gives examples, and retries blank required answers.
It creates no operational policy change; after preview you still review its
fingerprint before a separate apply. Do not enter secrets, tokens, or private
keys in either flow.

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

- [Local MCP](local-mcp.md): inspectable client fragments and profiles; Docker
  diagnostics are maintainer-only.
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
