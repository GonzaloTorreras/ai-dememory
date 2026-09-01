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
- `setup`, `remember`, `recall`, `review`, `status`, `module` and `serve`.
- Canonical Markdown, incremental SQLite FTS and review proposals.
- Lazy optional modules plus module scaffolding.
- Foreground MCP module with exactly five tools and no child process or socket.
- Focused V3 CI and cross-platform test matrix.

## Evidence

- Local compile passed with the bundled Python 3.12 runtime.
- The focused suite runs 46 tests: 43 pass locally and three symlink tests are
  skipped because this Windows account cannot create them. A real Windows
  junction containment test passes; hosted Linux CI executes the portable
  symlink cases.
- Hosted [CI run 33546063325](https://github.com/GonzaloTorreras/ai-dememory/actions/runs/33546063325)
  passed on Linux 3.11/3.13, macOS 3.12 and Windows 3.12. The preceding run
  exposed a Windows short-path assertion in the new test; `fa3eb19` normalized
  the expected path and the exact rerun passed.
- Clean `3.0.0a1` artifacts were rebuilt from the reviewed source: a 28,081-byte
  wheel and a 25,618-byte sdist. Their inventories contain only the V3 package, license,
  readmes and distribution metadata, with no V2 runtime, tests or scripts.
- The final wheel installed into a fresh virtual environment and completed
  setup -> human save -> JSON save -> lazy recall from outside the checkout.
  Both saves were read back, returned verified success and left SQLite absent;
  recall then created the generated index.
- SHA-256: wheel
  `7dfb75df06b6162d22efa9cb77d14ba61a3a3237aaf1f8dc0c47a8094ee81aff`;
  sdist `5e89ad01ff3756c5c4f03f99b02831a2f73a441ff5b723431d41af489a2cceaa`.
- Fresh exact product and security rereads found no remaining code blocker or
  P0-P2 finding after malformed-file, capacity, concurrent-lock, rollback and
  supplied-ID containment regressions were added.
- Residual risk: atomic file replacement does not fsync the parent directory
  against sudden power loss.

## Next

The vertical save MVP is independently reviewed and hosted-CI green. The
excluded V2 tree remains physically present but inert; physical deletion is a
separate one-time cleanup. Merge, tag and package publication remain explicit
gates.
