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
- `setup`, `remember`, `recall`, `review`, `status`, `module` and `serve`.
- Canonical Markdown, incremental SQLite FTS and review proposals.
- Lazy optional modules plus module scaffolding.
- Foreground MCP module with exactly five tools and no child process or socket.
- Focused V3 CI and cross-platform test matrix.

## Evidence

- Local compile passed with the bundled Python 3.12 runtime.
- The focused suite runs 48 tests: 45 pass locally and three symlink tests are
  skipped because this Windows account cannot create them. A real Windows
  junction containment test passes; hosted Linux CI executes the portable
  symlink cases.
- Hosted [CI run 33546224216](https://github.com/GonzaloTorreras/ai-dememory/actions/runs/33546224216)
  passed on Linux 3.11/3.13, macOS 3.12 and Windows 3.12. The preceding run
  exposed a Windows short-path assertion in the new test; `fa3eb19` normalized
  the expected path and the exact rerun passed.
- The last clean package evidence belongs to the save-MVP head `a32657e`.
  Because the local recall slice changes CLI output, artifacts must be rebuilt
  at the next push/release consolidation gate; no publication is requested.
- Fresh exact product and security rereads found no remaining code blocker or
  P0-P2 finding after malformed-file, capacity, concurrent-lock, rollback and
  supplied-ID containment regressions were added.
- Residual risk: atomic file replacement does not fsync the parent directory
  against sudden power loss.

## Next

The save MVP remains independently reviewed and hosted-CI green. The recall MVP
is locally complete; review/proposal UX is the next vertical slice. The excluded
V2 tree remains inert. Merge, tag and package publication remain explicit gates.
