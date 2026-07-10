# Changelog

All notable changes to ai-dememory are documented here. Release headings are
machine-validated and use the form `## [VERSION] - YYYY-MM-DD`.

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
