# Installation

This repository is the ai-dememory tool distribution repo. Users should install
the tool, then create a separate private memory vault.

PyPI currently serves stable `ai-dememory` 2.0.0. The public source tree declares
2.1.0, but those bytes are an unreleased development line until the immutable
tag, canonical release workflow, post-index verification, and explicit release
authorization are complete.

## Recommended User Install

Use `pipx` for normal CLI use because it installs Python applications in
isolated environments while keeping their commands on `PATH`.

Normal `ai-dememory --help` foregrounds vault, recall, working-memory, review,
and setup workflows. Advanced quality tooling plus maintainer-only CI,
distribution, release, and publishing commands live under
`ai-dememory dev --help`. Their historical top-level forms remain compatibility
aliases for existing automation.

```bash
pipx install ai-dememory
```

Equivalent `uv` tool install:

```bash
uv tool install ai-dememory
```

Upgrade later with:

```bash
pipx upgrade ai-dememory
```

If `pipx` is not available, use a virtual environment:

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install ai-dememory
```

PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
py -3 -m pip install ai-dememory
```

## From GitHub: Unreleased 2.1.0

PyPI is the normal installation source. To test an unreleased development
snapshot, install directly from GitHub:

```bash
pipx install git+https://github.com/GonzaloTorreras/ai-dememory.git
```

Use this path, rather than the stable PyPI install, to evaluate `setup wizard`,
resource intensity/model policy, generated MCP idle leases, and other 2.1.0
source behavior. Stable 2.0.0 does not contain those capabilities.

Or from a local checkout:

```bash
pipx install .
```

For contributor development, prefer editable install:

```bash
python3 -m pip install -e .
python3 -m unittest discover -s tests -t .
```

## Create A Vault

After installing:

```bash
ai-dememory init ~/code/my-memory
cd ~/code/my-memory
ai-dememory doctor
ai-dememory index
ai-dememory graph
ai-dememory setup plan --json
ai-dememory setup health --json
ai-dememory mcp-config --client codex
ai-dememory mcp-client-smoke
```

The generated vault is the repo users should keep private and sync with GitHub.
Do not store personal memory in the tool distribution checkout.

To create a reusable private GitHub vault template repository instead of a
single vault, export the packaged template:

```bash
ai-dememory vault-template export ~/code/ai-dememory-vault-template
```

Review the files, push them to a separate private repository, and mark that
repository as a GitHub template. The export command does not create or publish
the GitHub repository.

Package installation is passive. It does not install scheduler jobs, scan
provider folders, run the wizard, or enable hook recall/capture.

For a reviewable first-run checklist, use:

```bash
ai-dememory setup plan --json
```

That command is available in stable 2.0.0 and remains passive.

## Unreleased 2.1.0 Wizard And Profiles

This section describes the current public source line, not the stable 2.0.0
package. Install from GitHub or a local checkout as described above before
running these commands.

Then run `ai-dememory setup wizard` to preview a minimum baseline of values,
preferences, recommendations, and project profiles. Durable writes require
reviewer identity plus `--expect-plan-sha256 <preview fingerprint>` so changed
answers cannot be stamped reviewed without a new preview; reconfiguration
remains review-first.

The wizard also asks for two independent policies:

| Intensity | Recall per eligible turn | Scheduled cadence after explicit setup | Provider candidates/run | File/scan ceilings |
| --- | ---: | --- | ---: | --- |
| `minimal` | manual only | weekly | 5 | 32 KiB / 500 entries |
| `balanced` | up to 1,200 tokens | daily + weekly | 20 | 64 KiB / 2,500 entries |
| `active` | up to 2,400 tokens | daily + weekly | 50 | 128 KiB / 10,000 entries |

`balanced` is recommended for a first installation. Host-model policy is
separate: `off` permits deterministic local tools only, `advisory` lets the
already active host agent recommend, and `proposals` lets it create
review-first inbox proposals. ai-dememory runtime model calls and embedding
calls are zero in every option; host-agent token consumption is external and
still applies. No option installs integrations, captures raw payloads, or
promotes durable memory during the wizard.

## Optional Integrations And Setup Planning

Hook installation is separate and trust-gated. Generate a fragment with
`ai-dememory hooks config --client codex` or `--client claude`, inspect it, and
enable it only in a trusted repository. `hook-event dispatch` uses stdin JSON
and stdout JSON; invalid payloads or unavailable indexes fail open with `{}`.

The setup plan returns command arrays for MCP config, provider planning, hook
config, scheduler dry-run, reviewed cron export, maintenance, and manual
acceptance planning. It does not write files, install hooks, install schedules,
read provider chat files, or write import candidates. It also includes a
`generated_reports` command group for optional recall review, manual acceptance
plan, manual acceptance packet, recall review packet, hook capture review, and
release evidence handoff reports; those commands create generated files only
when the user runs them.
It also includes `generated_archive_status` commands for read-only recall and
manual acceptance packet archive inspection, and `generated_archive_retention`
commands for previewing generated packet archive cleanup candidates without
deleting files.
When recall review packet archives are enabled, use
`ai-dememory recall-fixtures packet-archive-status --json` to list generated
recall packet snapshots without promoting fixtures or writing files.
Use `ai-dememory recall-fixtures packet-archive-retention-plan --json` to
preview cleanup candidates without deleting files.
When manual acceptance packet archives are enabled, use
`ai-dememory acceptance packet-archive-status --json` to list generated packet
snapshots without recording evidence or writing files.
Use `ai-dememory acceptance packet-archive-retention-plan --json` to preview
cleanup candidates without deleting files.

For a combined read-only local status summary, use:

```bash
ai-dememory setup health --json
```

Setup health combines validation status, context config status, manual
acceptance readiness, recall review status, vector readiness, scheduler
environment/status, provider readiness, maintenance preflight commands and
artifact targets, generated artifact state, generated packet archive cleanup
counts, lock state, and review queues. It does not run commands, read provider
files, write files, or delete archives.

Readiness is dimensional: `core_ready` covers canonical validation and context
configuration; `retrieval_evaluated` requires fresh reviewed recall evidence;
`manual_maintenance_ready` covers a valid one-shot maintenance preflight;
`automation_ready` additionally requires a configured, fresh,
fingerprint-valid scheduler receipt that has been checked against the host;
`maintenance_ready` is the compatibility automation dimension;
`integrations_ready` covers configured provider/hook surfaces without malformed
captures; `autonomy_ready` combines verified automation, integrations, and a
valid bounded resource policy; and `release_ready` requires every release
dimension plus manual acceptance and clear review queues. This is a local
sign-off signal surfaced to the release owner, not a field consumed by the
canonical package workflow. `ready` is a deprecated alias for `core_ready`.

## Run As A Local MCP Server

Generate client config from inside the vault:

```bash
ai-dememory mcp-config --client codex
ai-dememory mcp-config --client claude
ai-dememory mcp-config --client generic
```

Run the server directly for a smoke test:

```bash
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"ping"}' | ai-dememory mcp --stdio
```

Docker is also supported for local stdio usage:

```bash
docker build -t ai-dememory:local .
ai-dememory mcp-config --client codex --mode docker --root ~/code/my-memory
ai-dememory mcp-client-smoke --mode docker --image ai-dememory:local --root ~/code/my-memory
```

See `docs/local-mcp.md` for MCP client and Docker examples.

## Run The Local REST API

For local scripts and dashboards that cannot use MCP stdio:

```bash
ai-dememory api --host 127.0.0.1 --port 8765
```

Set `AI_DEMEMORY_API_KEY` before binding to a non-loopback address. See
`docs/local-api.md`.

## Optional Maintenance And Provider Imports

Preview scheduler setup:

```bash
ai-dememory schedule plan --json
ai-dememory schedule plan --intensity minimal --json
ai-dememory schedule setup --dry-run
IMAGE_ID="$(docker image inspect --format '{{.Id}}' ai-dememory:local)"
ai-dememory schedule plan --json --mode docker --image "$IMAGE_ID"
ai-dememory schedule setup --dry-run --mode docker --image "$IMAGE_ID"
ai-dememory schedule cron
```

The plan includes the resolved vault root, exact command, vault-specific task
namespace, effective intensity, wall-clock/tree-cleanup policy, and
`plan_sha256`. Installation recomputes the exact projection before applying it,
then reads back and fingerprints the definitions it created.
`ai-dememory schedule status` refreshes verification only when the live
definitions still match, and cached host verification expires after five
minutes. Docker schedules require an immutable image ID/digest and add
`--network none` plus intensity-specific CPU, memory, and PID limits; installed
host mode does not claim native CPU/memory quotas.

Detect and configure chat/session providers:

```bash
ai-dememory providers detect
ai-dememory providers plan --json
ai-dememory providers configure codex --path "$HOME/.codex" --dry-run --json
ai-dememory providers configure codex --path "$HOME/.codex"
ai-dememory import-chats codex --dry-run --json
ai-dememory import-chats codex
```

Use the provider configure dry-run to review the selected folder before writing
`.ai-dememory.toml`. It normalizes the path and reports whether the folder
exists without reading provider chat files.
Bounded imports report `coverage_blocked` and a suggested larger scan window
when a truncated prefix contains only previously imported files.

Run maintenance manually:

```bash
ai-dememory maintenance run --profile daily --dry-run --json
ai-dememory maintenance run --profile daily
ai-dememory maintenance run --profile weekly
```

The maintenance dry-run previews enabled provider imports and generated
artifacts without writing inbox files, indexes, reports, or scheduler state.
Weekly maintenance also writes the generated sleep consolidation report at
`reports/sleep-plan.md` and the frontmatter-only hook capture review report at
`reports/hook-captures.md`.

See `docs/scheduler.md` and `docs/codex-plugin.md`.

## Publish Checklist

Before publishing a package:

- Confirm Apache-2.0 is the intended published license and that package
  metadata includes the license file.
- Run `ai-dememory install-smoke` from the distribution checkout to install the
  package in a fresh virtual environment and exercise a temporary private vault.
  This smoke includes provenance, acceptance status, generated MCP config,
  acceptance planning, doctor profile summary, CLI auto context from generated
  working memory, recall fixture promotion from a reviewed miss, lifecycle
  mark-seen and outcome receipts, working status, maintenance artifact status,
  vault template export, checked-in plugin MCP config launch, MCP
  enabled-tool verification, MCP release-evidence unavailability from a plain
  vault, and direct MCP `initialize`/`notifications/initialized`/`ping` with
  response-id matching, explicit missing-response diagnostics, and unexpected
  or invalid response-id rejection, including duplicates and result-less
  responses, plus non-object result and protocolVersion diagnostics.
  It removes generated package build metadata it creates during local install
  without deleting generated paths that already existed before the smoke.
- Run `ai-dememory package-build-smoke` from the distribution checkout to build
  wheel and source distributions into temporary storage and run `twine check`
  without leaving `dist/` artifacts in the repository.
  The smoke fails fast if stale generated `build/`, `dist/`, or
  `ai_dememory.egg-info/` paths already exist, so those artifacts must be
  removed before release validation.
- Run `ai-dememory mcp-client-smoke` from a configured vault to verify the
  generated installed-CLI MCP config launches, sends
  `notifications/initialized`, and responds to `initialize` and `ping`.
  Existing config-file smoke also verifies any `enabled_tools` entries against
  paginated `tools/list` output while matching responses by JSON-RPC id and
  skipping response-less server notifications.
- Verify `ai-dememory init`, `vault-template export`, `doctor`, `index`,
  `search`, `graph`, `mcp-config`, `providers detect`, `maintenance status`,
  `schedule plan --json`, `schedule setup --dry-run`, `eval-recall`,
  `api-smoke`, and `mcp --stdio` work outside the tool checkout.
  Install smoke validates that `schedule plan --json` includes scheduler
  commands, cron entries, and false side-effect flags.
- Run `ai-dememory install-smoke --skip-package --docker --image
  ai-dememory:local` to verify the Docker image against a bind-mounted vault
  and generated Docker MCP client config
  `initialize`/`notifications/initialized`/`ping` with response-id matching.
  Docker smoke also
  verifies `memory.release_evidence` reports unavailable from the plain mounted
  vault instead of fabricating distribution checkout evidence, and validates
  Docker `schedule plan --json`, `maintenance status` generated artifact and
  generated packet archive cleanup visibility, plus vault template export from
  the image.
- Run `ai-dememory dev publish-guard`, package/install smokes, and the release
  guard before merging the release PR.
- Obtain explicit user authorization for the exact release PR, version, merge,
  release tag, and consequent package publication.
- After that authorization, merge through protected `main` and wait for CI on
  the exact main commit. Then manually dispatch
  `.github/workflows/tag-release.yml` with `tag=v<version>`,
  `approved_sha=<40-character-main-sha>`, and
  `confirm=release-<tag>@<approved_sha>`. The workflow refuses a stale main
  commit, missing successful push CI, identity drift, or a conflicting tag,
  then stops after tag creation. Separately dispatch
  `.github/workflows/release.yml` with `intent=publish`, the same `tag` and
  `approved_sha`, and `confirm=publish-<tag>@<approved_sha>`. This second exact
  tuple is the publication authorization. Prerelease tags publish to TestPyPI,
  stable tags to PyPI, followed by post-index installation and GitHub Release
  verification.
- Never reuse or rewrite a published tag. Recovery uses the guarded
  `workflow_dispatch` path with `intent=recover` and
  `confirm=recover-<tag>@<approved_sha>` for the same immutable tuple; package
  rollback is yank plus fix-forward with a new version.

References:

- Python Packaging User Guide: https://packaging.python.org/
- pipx documentation: https://pipx.pypa.io/
