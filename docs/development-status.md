# Development status

Updated: 2026-09-01

## Current line

- Branch: `codex/product-reset-v3`
- Public base: `origin/main` at `e7f823ecf223d544b1f2f4cd909fbc42afb3aea3`
- Source version: `3.0.0a1`, unpublished
- Published stable: `2.1.1`, retained only as historical public evidence
- Migration/compatibility: deliberately none

## Implemented in the working slice

- New self-contained `src/ai_dememory` package with no runtime dependencies.
- Saved default vault usable from any working directory.
- First vertical MVP: `remember` atomically writes canonical Markdown, reads it
  back and reports success only after the stored fields match exactly.
- Saving is independent from SQLite; `recall` builds the disposable index only
  when search is requested.
- Second vertical MVP: `recall` works from the saved vault in any directory,
  reports an explicit match count and returns a clear empty result.
- Third vertical MVP: `review` exposes readable list/show/accept/reject results;
  acceptance saves verified Markdown without eagerly building SQLite.
- Fourth vertical MVP: the optional MCP module is enabled explicitly, serves
  read/proposal tools in one foreground process and exits cleanly on stdin EOF.
- Fifth vertical MVP: `status` reports useful vault state in readable text or
  JSON without building the disposable index or starting anything.
- `setup`, `remember`, `recall`, `review`, `status`, `module` and `serve`.
- Canonical Markdown, incremental SQLite FTS and review proposals.
- Lazy optional modules plus module scaffolding.
- Foreground MCP module with exactly five tools and no child process or socket.
- Focused V3 CI and cross-platform test matrix.

## Evidence

- Local compile passed with the bundled Python 3.12 runtime.
- The focused suite runs 55 tests: 52 pass locally and three symlink tests are
  skipped because this Windows account cannot create them. A real Windows
  junction containment test passes; hosted Linux CI executes the portable
  symlink cases.
- Hosted [CI run 33546224216](https://github.com/GonzaloTorreras/ai-dememory/actions/runs/33546224216)
  passed on Linux 3.11/3.13, macOS 3.12 and Windows 3.12. The preceding run
  exposed a Windows short-path assertion in the new test; `fa3eb19` normalized
  the expected path and the exact rerun passed.
- Clean `3.0.0a1` artifacts were rebuilt from local product head `8020c83` and
  installed without dependencies into a new virtual environment outside the
  checkout. The installed CLI completed setup, save, recall, readable status,
  module discovery, real MCP search/proposal, review acceptance and disable.
  Final installed state was two memories, zero proposals, zero background
  processes and zero model calls.
- Artifact evidence: wheel 28,781 bytes, SHA-256
  `ccb90f67376ccfab0acd7c415f7f30ca17ac1d5d40a80afbe45478bead8ce2b5`;
  sdist 26,497 bytes, SHA-256
  `31d2e21afe2c572f9ffcaed3a1569f5cf53bfb3ef1ca27cbe09dabc85df366e7`.
- Fresh review found and fixed one status-side-effect bug: inspection now opens
  an existing generated index as immutable read-only data and reports `invalid`
  instead of repairing it. The security reread found no P0-P3 issue.
- Residual risk: atomic file replacement does not fsync the parent directory
  against sudden power loss.

## Next

The save MVP remains independently reviewed and hosted-CI green. Five vertical
slices, the full local regression and installed-package smoke are complete. The
next action is fresh independent review before another push, followed by hosted
CI. The excluded V2 tree remains inert. Merge, tag and package publication remain
explicit gates.
