# Changelog

All notable changes to ai-dememory are documented here. In-development versions
use `## [VERSION] - Unreleased`. An explicitly authorized release-prep change
replaces `Unreleased` with the actual `YYYY-MM-DD`; only that dated form is
accepted by the release identity guard.

## [2.1.0] - Unreleased

- Canonicalize the public repository as the sole development and distribution
  source, keep historical private work as non-pushable review input, and make
  merge, tag, and publication authorization explicit while preserving
  independent technical review. Keep one immutable-tag package publisher and
  reduce the former manual publisher to a guarded read-only readiness preflight.
  Replace ambient post-CI tagging with a manual confirmation bound to the exact
  release tag and green current-main SHA. Keep the tagger unable to dispatch
  publication, remove ambient tag-push publication, and require a second manual
  intent/tag/SHA confirmation before the canonical publisher can run. Move
  checkout and Python setup to immutable Node 24-native v7 action pins.
- Keep Python 3.11+ as the authoritative domain and headless runtime; reserve
  Node/TypeScript for a future evidence-gated presentation plane with generated
  contracts and prebuilt assets.
- Add prompt-aware, project-aware reviewed recall hooks and a fingerprint-bound
  onboarding wizard for baseline values, preferences and recommendations.
  Preserve each recalled item's sensitivity label in structured and rendered
  context so public-repository egress policy remains enforceable.
- Add `minimal`, `balanced`, and `active` resource intensities with hard recall,
  import, scan, report, timeout, hook-queue, scheduler, and Docker ceilings.
  Keep host-model policy separate, report zero runtime model/embedding calls,
  and reject automatic durable promotion.
- Make generated private-vault MCP configs vault-bound and four-tool `core` by
  default, while the checked-in public plugin uses a server-enforced three-tool
  public-only ceiling. Namespace scheduler jobs per vault, require
  exact plan fingerprints, create host definitions without forced replacement,
  persist exact root/command/projection/readback evidence with expiring host
  verification, preserve original namespaces and definition paths after vault
  moves, reject copied receipts while the original vault still owns the same
  enabled namespace and plan, keep receipted cadence/intensity removable after policy changes,
  restore exact Windows task XML, reject mutable unattended Docker images, and compensate
  failed install/remove transactions. Fail closed before command generation and
  again before scheduler writes when the resource policy is invalid, returning
  its exact validation diagnostics instead of installing jobs that cannot run.
- Add MCP idle self-leases, per-response deadlines, non-interactive Git,
  bounded child output/time, suspended-before-assignment Windows kill-on-close
  Job Objects, and POSIX owned
  process sessions so timeout, leader exit, or client disconnect cannot leave
  package-owned descendants running.
- Bound canonical discovery, secret scans, graph pages/nodes/edges, MCP input
  frames/queues, and SQLite audit histories. Stream secret scanning and index
  state restoration, paginate graph delivery, safely fence raw hook payloads,
  and surface truncated provider windows that can no longer make progress.
- Add a fail-closed public-only recall ceiling across context, search, and get:
  filter before result limits, ignore hostile sensitivity overrides, omit
  generated working state and rejected identifiers, and reject auto-query
  derivation for public output.
- Version local manual acceptance evidence and require revision 3 for
  `testpypi-publish`, invalidating legacy passes from the former manual
  publisher and retired tag-push topology without deleting their audit history;
  this remains sign-off evidence rather than a package-workflow gate.
- Make path handling and the unit-test matrix portable across Linux, macOS and
  Windows while preserving symlink and vault-boundary protections.
- Avoid repeated canonical-root resolution while scanning repository text for
  secret-like findings, reducing read-only maintenance status overhead without
  weakening the scanner pattern set.
- Separate setup readiness into core, retrieval, manual maintenance, verified
  automation, integration, autonomy and release dimensions, and ignore inbox
  documentation when parsing captures.
- Introduce bounded MCP tool profiles with a small default core surface, plus
  clearer user and maintainer CLI command groups.
- Stabilize imports from the installed wheel and extend isolated-package smoke
  coverage. Modernize package-license metadata to PEP 639 with an SPDX
  expression and declared license file. Recall quality remains evidence-gated
  until real misses are reviewed and promoted into the evaluation corpus.

## [2.0.0] - 2026-07-10

- Publish the first clean public source snapshot under Apache-2.0 after three
  successful release-candidate cycles through TestPyPI.
- Ship the local-first CLI, MCP server, Codex plugin, vault templates, release
  guards, package smokes, scheduler planning, review queues and recall tooling.
- Prevent package namespace collisions with the official MCP SDK, emit native
  Codex TOML, and distinguish missing recall evidence from successful recall.
- Establish tag-driven Trusted Publishing with exact-artifact smoke tests,
  checksums, attestations, post-index installation and GitHub Releases.

## [2.0.0rc3] - 2026-07-10

- Prevent the wheel from installing top-level `mcp` or `scripts` packages and
  verify coexistence with the official MCP SDK across supported Python versions.
- Require Python 3.11+, emit native Codex TOML configuration, and treat empty
  recall evaluation as insufficient evidence instead of perfect recall.

## [2.0.0rc2] - 2026-07-10

- Make recovery idempotent only when TestPyPI/PyPI filenames and SHA-256
  digests exactly match the locally rebuilt release bundle.
- Bind GitHub Release creation explicitly to the canonical repository.

## [2.0.0rc1] - 2026-07-10

- Exercise the complete AI-operated Trusted Publishing path on TestPyPI.
- Verify OIDC identity, exact-artifact smoke, checksums, attestations,
  post-index installation and GitHub prerelease creation before stable launch.
