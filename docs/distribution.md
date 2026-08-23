# Distribution Plan

## Repository Roles

Use two repository types:

1. `ai-dememory`: this tool distribution repo.
2. User memory vault repos: private repositories containing personal Markdown
   memory and generated local artifacts.

Users should not fork `ai-dememory` to store memory. Forking mixes private data
with upstream tool code, complicates upgrades, and makes accidental disclosure
more likely.

**Release scope:** 2.1.1 is source release preparation, not an installable route until tag-bound PyPI publication and external readback complete. 2.1.0 is the currently published PyPI compatibility route while release verification is pending.

## Recommended Channels

### Primary: PyPI package

Publish `ai-dememory` as a Python application package with the
`ai-dememory` console script. Users install with:

```bash
pipx install ai-dememory==2.1.0
```

This keeps application dependencies isolated and makes upgrades simple.

`uv` users can install the same package with:

```bash
uv tool install ai-dememory==2.1.0
```

### Source checkout: contributors only

Contributor development is documented in `DEVELOPMENT.md`. It is not a user
installation route or a fallback for the published package.

### Vault creation: CLI template

The package includes a vault template and exposes:

```bash
ai-dememory init ./my-memory --wizard --require-version 2.1.0
```

This is the concise wizard-first setup path for the published 2.1.0 package.
The compatibility flag is required until the pending stable publication is
verified and the user documentation can be promoted separately.

### Optional: GitHub template repo

Create a separate repository such as `ai-dememory-vault-template` from the
contents of `vault-template/`.

The installed CLI can export the same packaged vault template without requiring
users to clone the tool distribution repo:

```bash
ai-dememory vault-template export ./ai-dememory-vault-template
```

Users who prefer GitHub UI setup can choose "Use this template", create a
private repository, clone it, then install the tool separately.

`vault-template/` is intentionally mirrored with the packaged template under
`ai_dememory_tool/templates/vault/`; release checks and tests fail if the two
trees drift.

### Optional later: npm wrapper

An npm package is only useful if users strongly prefer `npx` for MCP setup. If
added, it should be a thin wrapper that checks for Python and delegates to the
Python package instead of reimplementing the toolchain.

### Optional later: Codex skill or marketplace entry

A skill can teach Codex how to use an installed `ai-dememory` command and a
user vault. It should be onboarding glue, not the primary distribution mechanism
for the CLI.

### Docker source-image diagnostics: maintainers only

The repository Dockerfile supports isolated CI and release diagnostics from a
trusted checkout. It is not a distribution channel while 2.1.1 is still pending
tag-bound PyPI publication and external readback: building `ai-dememory:local`
would run unpublished source instead of the published 2.1.0 package. Users
should use the installed CLI and its generated MCP configuration; the eventual
Docker mode remains local-only, with no exposed ports, after its separately
verified release route is documented.

## Setup UX Target

```bash
pipx install ai-dememory==2.1.0
ai-dememory init ~/code/my-memory --wizard --require-version 2.1.0
```

The wizard chooses a bounded resource policy and writes the vault-local
configuration. Connecting a client is a separate, optional action because the
generated fragment must be inspected before it is copied into host config:

```bash
ai-dememory --root ~/code/my-memory mcp-config --client codex
```

`ai-dememory --version` is the ordinary confirmation after an install or
upgrade. The `version-check` subcommand remains available for CI or
support diagnostics; it is not part of first-run setup.

The published compatibility route is the only user-facing setup route while
release verification is pending.

## Stable Release Requirements

- Keep Apache-2.0 as the declared license for code, docs, templates, and
  packaged vault scaffolding unless a separately reviewed release changes it.
  Declare it with PEP 639 `project.license` and `project.license-files` metadata
  rather than deprecated TOML tables, setuptools-only fields, or license
  classifiers.
- Keep PyPI and TestPyPI Trusted Publishers bound to
  `.github/workflows/release.yml` with their matching `pypi` and `testpypi`
  GitHub environments.
- Require an RC to install successfully from TestPyPI and pass the isolated
  wheel namespace/coexistence matrix before a stable tag is created.
- Keep Docker support local-only unless an authentication and authorization
  design is approved for remote MCP.

## Publishing Workflow

The canonical publisher is `.github/workflows/release.yml`, dispatched manually
for an already created immutable version tag and its exact commit. A tag push
alone never invokes the current publisher. Prerelease tags publish only to
TestPyPI; stable tags publish only to PyPI. The workflow creates the matching
GitHub Release after the package can be installed back from its target index.

`.github/workflows/publish.yml` is retained only as a legacy hosted readiness
preflight. It has read-only repository permission, disables persisted checkout
credentials, and cannot build a release artifact, request OIDC, target a package
environment, upload, create a release, push a tag, or publish. Its explicit
confirmation value is `preflight`.

The preflight runs
`publish-guard`, `artifact-guard`, `validate`, `secret-scan`, `verify-mcp`, and
`release-check`, followed by installed-package smoke, package build smoke with
`--check-clean`, Docker local MCP smoke, and strict readiness planning. Any
artifacts created inside smoke isolation are discarded with the workflow and
are never passed to a publisher.
Installed-package and Docker smoke both validate the read-only scheduler plan
payload, including scheduler commands, cron entries, and false side-effect
flags, before any package can be published.

Before running the workflow, verify the workflow safety contract locally:

```bash
ai-dememory publish-guard
ai-dememory publish-plan --repository testpypi --pr-url https://github.com/... --json
ai-dememory publish-plan --repository testpypi --pr-url https://github.com/... --strict
ai-dememory artifact-guard
ai-dememory package-build-smoke
```

The canonical package path is the exact-tuple dispatch flow documented in
[AI-operated releases](ai-operated-releases.md). Codex prepares and verifies
the release PR and may merge it under the standing repository delegation only
after strict CI, a fresh exact-head `READY` review, and the tuple-bound receipt
defined in [Sole-maintainer review](solo-maintainer-review.md). That merge does
not authorize a tag or publication. The manual tagger may create the immutable
version tag and stop only after explicit user authorization for that exact tag
and commit. A second explicit dispatch of `.github/workflows/release.yml`, bound
to the same tag and commit, separately authorizes publication. The publisher
validates tag/version/changelog identity, builds once, smokes the exact wheel
and sdist, attests them, publishes through OIDC, verifies the index install, and
creates the GitHub Release.

The older `publish.yml` and `publish-plan` interfaces are retained as a
read-only compatibility and diagnostic surface during migration. PyPI Trusted
Publisher identities must point only at `release.yml`, so this legacy workflow
cannot become an alternate publication path.

`publish-plan` reports the legacy preflight inputs, target index under
evaluation, resolved GitHub Actions URL when the local remote is a GitHub repo,
read-only commands, guard issues, release-evidence blockers, and false
publication side-effect flags. The existing `publish_ready` field is retained
for API compatibility; it is readiness evidence for the canonical tag path,
not permission or capability to publish from `publish.yml`. TestPyPI readiness
may defer only its post-publish acceptance record; within this local planner,
PyPI readiness requires the full evidence set after TestPyPI verification.
Neither `publish_ready` nor `release_ready` is consumed by `release.yml`,
which cannot read private-vault acceptance receipts. Missing local evidence is
instead disclosed to the owner before explicit release authorization.

The plan may run local inspection commands to read git status and the
configured remote, but it does not run publish workflow commands, run preflight
commands, write files, upload packages, or contact package registries. Plain
vaults and non-GitHub remotes keep a placeholder workflow URL.

`package-build-smoke` builds into temporary storage, but refuses to start when
stale generated `build/`, `dist/`, or `ai_dememory.egg-info/` paths already
exist in the checkout. Remove those generated artifacts before release
validation so stale local build state cannot mask package build failures.

The guard checks that canonical package publishing is exact-tag-bound,
workflow-dispatch-only, concurrency controlled, build-once, exact-artifact
tested, checksummed, attested and bound to the `testpypi` and `pypi` OIDC
environments. It also checks the green-CI tagger cannot dispatch the publisher
and ensures the compatibility workflow remains manual and token-free.
The artifact guard checks staged
Git paths so generated SQLite, report, context export, build, and cache files do
not ship with the release branch.

For a PR or release handoff, generate a readiness snapshot:

```bash
ai-dememory release-evidence --write-report \
  --reviewer "Reviewer Name" \
  --pr-url https://github.com/...
ai-dememory release-evidence --strict \
  --reviewer "Reviewer Name" \
  --pr-url https://github.com/...
```

The evidence report summarizes automated release gates and lists manual
acceptance items that still require human proof. `--strict` exits nonzero until
the worktree is clean, automated release checks have no warnings or failures,
and all manual acceptance items have reviewed passing evidence.
`--reviewer` can also come from `AI_DEMEMORY_REVIEWER`, and `--pr-url` can
come from `AI_DEMEMORY_PR_URL`. When present, release evidence propagates that
metadata into `manual_acceptance_plan` and the top-level `handoff_commands`,
including `acceptance_plan`, `acceptance_template`, manual acceptance packet,
recall packet, and strict release-evidence command arrays. The metadata is
handoff guidance only; it does not authenticate the reviewer or record proof.
The JSON and Markdown report also include a top-level `next_actions` list and
`manual_acceptance_plan`, which mirrors `ai-dememory acceptance plan` and
provides example `acceptance record` commands for each remaining or blocked
item. Plan rows also include `suggested_artifacts`, so release reviewers can
attach client logs, reviewed inbox paths, maintenance reports, or publish
workflow URLs instead of guessing what proof is expected.
Use `release_blockers` in the same output to see the exact categories keeping
`release_ready` false, including dirty worktree state, automated warnings or
failures, recall review when current eval is unavailable or failing, vector
readiness review, and manual acceptance blockers. Stale seed-only recall
fixtures remain visible in `recall_fixture_freshness` and
`recall_fixture_review_plan`, but a clean current eval with no pending or
invalid miss files is release evidence rather than a blocker. `vector_readiness`
is evidence-only and reports
`creates_embeddings=false`; a `vector_readiness_review` blocker only appears
when measured recall failures make a vector experiment eligible for review.
The report also embeds `setup_health_summary` and `maintenance_summary`, compact
read-only views of local setup and maintenance state covering validation,
context defaults, scheduler readiness, hook capture review counts, provider
readiness, recall review, vector readiness, generated artifacts, review queues,
generated artifact freshness, generated packet archive cleanup counts, and next
actions. It does not install hooks or schedules, run maintenance, refresh
generated artifacts, delete archives, apply recommendations, or record manual
acceptance evidence.

For recall-quality release handoffs, use
`ai-dememory recall-fixtures packet --reviewer "Reviewer Name" --pr-url
https://github.com/... --write-report` to pre-fill reviewer and PR context while
keeping fixture promotion and miss closure as separate reviewed commands. Use
`ai-dememory recall-fixtures packet-archive-status --json` to list generated
recall packet snapshots without writing files or promoting fixtures.

Codex is the operational release owner: it may prepare changes, evidence,
reviews, versioning, changelog and fix-forward plans. Merge, immutable tag
creation and Trusted Publisher execution remain explicit user-approved actions
even when every automated gate passes. Account recovery, legal ownership,
billing, visibility, destructive changes, and trusted-publisher identity changes
remain human break-glass operations.

After the release owner or another reviewer completes one of those manual
checks, record reviewed evidence:

```bash
ai-dememory acceptance record \
  --item mcp-client-installed \
  --reviewed-by "Reviewer Name" \
  --summary "Generated config was used with a real MCP client." \
  --artifact "https://github.com/GonzaloTorreras/ai-dememory/pull/<number>"
ai-dememory acceptance status
ai-dememory acceptance plan
ai-dememory acceptance plan --write-report
ai-dememory acceptance packet --write-report
ai-dememory acceptance packet --limit 50 --offset 50 --write-report
ai-dememory acceptance verify
ai-dememory release-evidence --write-report
```

Use `ai-dememory release-evidence --write-report --report-path
reports/v2-release-evidence.md` when the handoff needs an explicit generated
report path. The path must remain inside the memory root and the rendered
Markdown is secret-scanned before writing.

`acceptance plan` is read-only. It shows remaining and blocked manual checks and
example `acceptance record` commands plus suggested evidence artifacts without
writing evidence.
`acceptance plan --write-report` writes the same planning output to
`reports/manual-acceptance-plan.md` so a release handoff can attach a concrete
generated artifact. It is still not acceptance evidence; it only tells the
reviewer what proof to collect before running `acceptance record`.
`acceptance packet --write-report` writes
`reports/manual-acceptance-packet.md`, a fill-in review packet for every
incomplete manual acceptance item. It includes suggested artifacts and pass/block
record commands, but still does not record evidence. Use `--limit` and
`--offset` to page large incomplete-item sections. Use `--reviewer` and
`--pr-url` when the packet should carry release handoff metadata for a reviewer
or draft PR. Add `--archive` when a release handoff needs a timestamped
generated packet copy under `reports/manual-acceptance-packets/`.
`acceptance packet-archive-status --json` lists those generated snapshots with
pagination metadata and remains read-only; it does not record acceptance
evidence.
Use `ai-dememory acceptance template --item <item-id>` to print a single
review note template before completing the check. It is read-only and does not
count as acceptance evidence until a reviewer runs `acceptance record`.
Add `--reviewer "Reviewer Name"` and `--pr-url https://github.com/...` to
`acceptance plan` or `acceptance template` when a release handoff should
pre-fill reviewed-by and PR artifact fields in generated record commands
without recording evidence.
The same metadata can be supplied once to `ai-dememory release-evidence`; the
embedded manual acceptance plan and handoff commands will carry it forward.

If a manual acceptance check is attempted but blocked by the local environment
or an external dependency, record reviewed blocker evidence:

```bash
ai-dememory acceptance record \
  --item mcp-client-docker \
  --status blocked \
  --reviewed-by "Reviewer Name" \
  --summary "Docker is unavailable on this workstation."
ai-dememory release-evidence --write-report
```

Blocked records are shown separately in release evidence and remain part of the
remaining manual acceptance work until a `passed` record exists.
`ai-dememory acceptance verify` exits nonzero while any manual acceptance item
is remaining or blocked, and exits zero only after every item has passing
reviewed evidence.

Acceptance records are Markdown files under `inbox/release-acceptance/`.
They are secret-scanned before writing and remain separate from automated
release gates.
