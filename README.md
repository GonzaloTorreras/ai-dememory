# ai DeMemory

ai DeMemory is a local-first, review-first memory tool for Codex, Claude,
Gemini, Obsidian, and future clients. Install the Python CLI, create a
separately bound private vault, and keep Markdown as the human-editable source
of truth.

This public repository distributes the tool, documentation, and public
demo/validation fixtures. It is not a personal vault: private memories,
credentials, and local receipts belong in a separately bound private location.
SQLite FTS, exports, reports, and future vector indexes are generated from
Markdown and can be rebuilt.

## Choose Your Path

- **Install the tool and create a private vault:** follow [Quick Start](#quick-start).
- **Connect an AI client or run a local dashboard/script:** use
  [Use It Locally](#use-it-locally) after the wizard.
- **Find a focused guide:** start at the [documentation portal](docs/README.md).
- **Work on the source checkout, tests, or releases:** read
  [Source Checkout And Contributor Workflows](#source-checkout-and-contributor-workflows).

## Release Status

- Current release line: `ai-dememory` 2.1.0.
- 2.1.1 is source release preparation, not an installable route until tag-bound PyPI publication and external readback complete.
- 2.1.0 is the currently published PyPI compatibility route while release verification is pending.
- The published stable 2.1.0 package is the only user-installable route in this interim state.
- MCP protocol baseline: stable `2025-11-25`, with `2024-11-05` accepted for
  older clients.
- Python 3.11+ is the only headless runtime. Node is not an installation or
  background-process dependency; see
  [the runtime boundary](docs/adr/0254-python-node-runtime-boundary.md).
- Transport is local MCP stdio plus an optional local REST API. Remote HTTP,
  OAuth, automatic durable writes, and vector search are out of scope for this
  release.

The [public modernization roadmap](docs/public-modernization-roadmap.md)
describes product direction. Source-site delivery, planning, and release
operations are contributor material, not installation steps.

## Quick Start

### Published 2.1.0: compatibility setup

Install the exact published package and create a separate private vault with its
version-gated wizard:

```bash
pipx install ai-dememory==2.1.0
ai-dememory init ~/code/my-memory --wizard --require-version 2.1.0
```

The wizard previews its plan, shows resource limits, and asks before it writes
the vault operational config. It never imports chats, creates personal memory,
installs hooks or schedules, or edits a client configuration.

The complete instructions live in the [installation guide](docs/install.md).
The compatibility gate is required by the published 2.1.0 wizard; it is not a
separate diagnostic ritual. A post-publication documentation update will promote
the clean 2.1.1 wizard path only after the protected workflow and package-index
readback succeed.

`uv` users can substitute `uv tool install ai-dememory==2.1.0` for the first
line. On Windows, use a private path such as `D:\Memory\my-vault` instead of
the example path.

### Connect a client when you are ready

Client configuration is a separate, explicit action: inspect the generated
fragment before copying it into Codex, Claude, or another host.

```bash
ai-dememory --root ~/code/my-memory mcp-config --client codex
```

The generated fragment binds the vault, uses the reduced server-enforced
`core` profile, and sets an idle lease. You do not need to type its internal
runtime arguments during first-run setup.

### Update or diagnose an installation

For an existing pipx install, repair it with the same immutable package pin.
`--version` is the normal diagnostic when you need to confirm what is on PATH;
`version-check` remains available for CI and compatibility diagnostics, not as a
required user ritual.

```bash
pipx install --force ai-dememory==2.1.0
ai-dememory --version
```

To create a reusable private GitHub vault template rather than one local vault:

```bash
ai-dememory vault-template export ~/code/ai-dememory-vault-template
```

Review the exported files, then keep that vault repository private and separate
from the public tool distribution repository.

## Use It Locally

The wizard creates a private vault and its bounded local policy; it neither
launches a local API nor changes host configuration. The MCP configuration
above uses stdio, not a network port. Generated client configuration includes a
bound vault, a reduced tool profile, and an idle lease; see [Local MCP](docs/local-mcp.md)
and [MCP client configuration](docs/mcp-client-config.md) for the full setup.

For a local script or dashboard that needs HTTP rather than MCP stdio, run the
optional REST API from the installed command:

```bash
ai-dememory --root ~/code/my-memory api
```

It runs in the foreground, binds only to `127.0.0.1:8765` by default, and stops
with Ctrl-C. It is not started automatically. The [local API guide](docs/local-api.md)
covers endpoint details, indexing, and the stricter API-key/TLS requirements
for any deliberate non-loopback binding.

## Documentation By Task

The [documentation portal](docs/README.md) separates first use, local MCP/API
operation, maintenance, architecture, and source/release material. Start there
instead of treating every repository command as an installation requirement.

## Source Checkout And Contributor Workflows

This section is for people working on a trusted source checkout, tests, or
release evidence. It is not part of a normal `pipx` installation or wizard
first run. The installed `ai-dememory` command is the normal private-vault
interface; compatibility wrappers and direct script modules belong only to
source debugging and CI.

- [Documentation portal](docs/README.md): choose the relevant user, operations,
  architecture, or contributor guide.
- [Maintainer script reference](scripts/README.md): checkout-only test, CI, and
  compatibility-wrapper guidance.
- [Draft PR handoff](docs/pr-draft.md): required evidence and exact-head PR
  workflow.
- [v2 release checklist](docs/release-v2-checklist.md): release and package
  evidence gates.
- [Development continuity](DEVELOPMENT.md) and
  [current development status](docs/development-status.md): public frontier,
  branch, and approval boundary.

On Windows PowerShell, contributor instructions use `py -3` where their
equivalent says `python3`. Do not copy source-checkout test or release commands
into a personal vault workflow.

## Architecture

- Markdown and Obsidian are the human-editable source of truth.
- A separately chosen private Git repository can sync and version canonical
  memory; the public tool repository does not contain that memory.
- SQLite FTS5 is the local retrieval and ranking layer; graph, reports, and
  future vector indexes are generated and disposable.
- MCP exposes local recall and review-first proposal tools. The optional REST
  API serves local dashboards and scripts that cannot launch MCP stdio.
- Vector search remains optional and requires measured recall evidence before
  it can add a dependency or privacy surface.

See [architecture](docs/architecture.md), [schema](docs/schema.md),
[operations](docs/operations.md), and [source-grounded query design](docs/source-grounded-query-design.md).

## Safety Model

- Never store secrets, tokens, private keys, service-account JSON, cookies,
  recovery codes, or `.env` contents in a vault or this repository.
- Durable memory changes require human review. LLMs may create proposals in
  `inbox/llm-captures/`, not direct durable writes.
- Generated indexes, context exports, and reports can be rebuilt from canonical
  Markdown; they are not durable memory by themselves.
- Secret scanning and schema validation run before indexing.
- `private` and `sensitive` memories are excluded from default search, MCP
  results, and generated context unless a local user explicitly includes them.
- `internal` memory can be valid in a private vault but is not public-safe.
  Public-repository work must request the fail-closed `public_only` ceiling.

## Public Source Repository Layout

This describes the public checkout and its demo/validation fixtures. A real
vault is separately bound and must not be added to this repository.

- `memories/` and `inbox/`: public fixtures and review candidates, never a
  personal memory archive.
- `working/`, `indexes/`, `distilled/`, and `reports/`: generated state,
  indexes, exports, and review output.
- `mcp/`: MCP server implementation and integration notes.
- `scripts/`: maintainer validation, retrieval, integration, and release tools.
- `templates/` and `vault-template/`: starter content for a private vault.
- `contracts/planning/`: normative V3 task order and state; historical research
  in `PLAN.md` is explanatory, not an executable backlog.

## MCP v2 Operation

For normal local use, generate a bound client configuration through the command
in Quick Start. The default `core` profile exposes four server-enforced tools;
the checked-in public plugin is stricter and uses a three-tool `public` profile
with `public_only=true`, no sensitive content, and no working-memory injection.
`working` and `review` are opt-in, while `admin` preserves the complete
historical MCP surface for compatibility and broad maintenance.

MCP resources do not expose `private`, `sensitive`, or `secret-prohibited`
memory by default. Tools that could include sensitive content require an
explicit opt-in, and proposal/review actions remain confined to review-first
locations. The server is stdio-only; do not expose it as a network service
without a separate authentication and authorization design.

The following machine-checked inventory is collapsed so it does not obscure
the normal installation path. The complete protocol explanation and profile
measurements are in [MCP V2](docs/mcp-v2.md),
[MCP tool profiles](docs/mcp-tool-profiles.md), and
[the protocol gap analysis](docs/mcp-v2-gap-analysis.md).

<details>
<summary>Maintainer inventory: 74 MCP tools</summary>

Implemented MCP surface: 74 MCP tools.

- `memory.search`, `memory.get`, `memory.write_proposal`,
  `memory.mark_seen`, `memory.reindex`, `memory.consolidate`,
  `memory.secret_scan`, `memory.graph`, `memory.doctor`,
  `memory.validate_status`, `memory.capture_miss`,
  `memory.recall_miss_candidate`,
  `memory.recall_fixture_status`, `memory.recall_review_plan`,
  `memory.recall_review_packet`,
  `memory.recall_review_packet_archive_status`,
  `memory.recall_review_packet_archive_retention_plan`,
  `memory.recall_miss_review`,
  `memory.vector_status`, `memory.roadmap_status`, `memory.context`,
  `memory.outcome`, `memory.lifecycle_scores`, `memory.maintenance_status`,
  `memory.import_chats`, `memory.capture_import`, `memory.git_lessons`,
  `memory.maintenance_run`, `memory.schedule_plan`,
  `memory.schedule_status`, `memory.schedule_environment`,
  `memory.hook_events`, `memory.hook_config`, `memory.hook_status`,
  `memory.hook_capture_review`, `memory.sleep_plan`,
  `memory.sleep_apply_reviewed`, `memory.working_current`,
  `memory.working_status`, `memory.working_snapshot`,
  `memory.working_handoff`, `memory.providers_detect`,
  `memory.providers_status`, `memory.providers_plan`, `memory.setup_plan`,
  `memory.setup_health`, `memory.review_false_positives`,
  `memory.review_stale_false_positives`, `memory.false_positive_ignore`,
  `memory.false_positive_unignore`, `memory.review_conflicts`,
  `memory.conflict_dismiss`, `memory.conflict_keep`,
  `memory.conflict_merge_proposal`, `memory.review_modes`,
  `memory.review_configure_mode`, `memory.review_plan`,
  `memory.review_recommendation`, `memory.review_recommendations`,
  `memory.review_recommendation_archive_status`,
  `memory.review_recommendation_archive_restore_preview`,
  `memory.review_recommendation_outcome_report`,
  `memory.review_recommendation_outcome`, `memory.provenance_status`,
  `memory.acceptance_status`, `memory.acceptance_verify`,
  `memory.acceptance_plan`, `memory.acceptance_template`,
  `memory.acceptance_packet`,
  `memory.acceptance_packet_archive_status`,
  `memory.acceptance_packet_archive_retention_plan`,
  `memory.release_evidence`, `memory.release_evidence_report`, and
  `memory.publish_plan`.

</details>

## Working In A Private Vault

After creating a separate private vault:

1. Capture new information as Markdown in `inbox/` or an appropriate
   `memories/` folder.
2. Validate and secret-scan it before indexing.
3. Rebuild the disposable SQLite index when you want it searchable.
4. Search or assemble bounded context for an LLM session.
5. Promote proposals into durable, project, or active memory only after review.

For imports, hooks, schedulers, maintenance, review packets, and recovery,
follow the focused guides in the [documentation portal](docs/README.md). Those
actions are opt-in and are not performed by installation or the wizard.

## Source Validation And Release Gates

Source validation, CI, draft PR evidence, package smoke, release identity, and
manual acceptance are maintained outside this product entry page. Use the
[maintainer script reference](scripts/README.md), [draft PR handoff](docs/pr-draft.md),
and [v2 release checklist](docs/release-v2-checklist.md) for the exact command
sets and evidence order.

CI validates the source, schema, secret policy, MCP contract, package smoke,
and generated-artifact boundary. Generated SQLite databases, context exports,
and reports are never canonical memory and are not staged unless a change
explicitly reviews them.

Review, merge, and release authority is documented in
[Development continuity](DEVELOPMENT.md) and the
[draft PR handoff](docs/pr-draft.md). A private vault is never release evidence
or public repository content.
