# Changelog

All notable changes to ai-dememory are documented here. Release headings are
machine-validated and use the form `## [VERSION] - YYYY-MM-DD`.

## [2.1.0] - 2026-07-11

- Add prompt-aware, project-aware reviewed recall hooks and a fingerprint-bound
  onboarding wizard for baseline values, preferences and recommendations.
- Make path handling and the unit-test matrix portable across Linux, macOS and
  Windows while preserving symlink and vault-boundary protections.
- Separate setup readiness into core, retrieval, maintenance, integration and
  release dimensions, and ignore inbox documentation when parsing captures.
- Introduce bounded MCP tool profiles with a small default core surface, plus
  clearer user and maintainer CLI command groups.
- Stabilize imports from the installed wheel and extend isolated-package smoke
  coverage. Recall quality remains evidence-gated until real misses are reviewed
  and promoted into the evaluation corpus.

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
