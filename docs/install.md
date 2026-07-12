# Installation

This repository is the ai-dememory tool distribution repo. Users should install
the tool, then create a separate private memory vault.

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

## From GitHub

PyPI is the normal installation source. To test an unreleased development
snapshot, install directly from GitHub:

```bash
pipx install git+https://github.com/GonzaloTorreras/ai-dememory.git
```

Or from a local checkout:

```bash
pipx install .
```

For contributor development, prefer editable install:

```bash
python3 -m pip install -e .
python3 -m unittest discover -s tests
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
ai-dememory setup wizard
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

Then run `ai-dememory setup wizard` to preview a minimum baseline of values,
preferences, recommendations, and project profiles. Durable writes require
reviewer identity plus `--expect-plan-sha256 <preview fingerprint>` so changed
answers cannot be stamped reviewed without a new preview; reconfiguration
remains review-first.

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
`maintenance_ready` covers scheduler and generated artifacts;
`integrations_ready` covers configured provider/hook surfaces without malformed
captures; and `release_ready` requires every dimension plus manual acceptance
and clear review queues. `ready` is a deprecated alias for `core_ready`.

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
ai-dememory schedule plan --json --mode docker --image ai-dememory:local
ai-dememory schedule setup --dry-run
ai-dememory schedule setup --dry-run --mode docker --image ai-dememory:local
ai-dememory schedule cron
```

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
- Merge through protected `main`. After CI succeeds on that exact commit,
  `.github/workflows/tag-release.yml` derives and creates the immutable
  matching tag (`v<version>`); do not race it with a manual tag.
  `.github/workflows/release.yml` is the canonical AI-operated Trusted
  Publishing path: prerelease tags publish to TestPyPI, stable tags to PyPI,
  followed by post-index installation and GitHub Release verification.
- Never reuse or rewrite a published tag. Recovery uses the guarded
  `workflow_dispatch` path for the same immutable tag; package rollback is yank
  plus fix-forward with a new version.

References:

- Python Packaging User Guide: https://packaging.python.org/
- pipx documentation: https://pipx.pypa.io/
