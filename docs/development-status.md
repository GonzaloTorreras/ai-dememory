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
- `setup`, `remember`, `recall`, `review`, `status`, `module` and `serve`.
- Canonical Markdown, incremental SQLite FTS and review proposals.
- Lazy optional modules plus module scaffolding.
- Foreground MCP module with exactly five tools and no child process or socket.
- Focused V3 CI and cross-platform test matrix.

## Evidence

- Local compile passed with the bundled Python 3.12 runtime.
- The focused suite runs 39 tests: 36 pass locally and three symlink tests are
  skipped because this Windows account cannot create them. A real Windows
  junction containment test passes; the Linux CI matrix will execute the
  symlink cases.
- Clean `3.0.0a1` artifacts were rebuilt: a 27,048-byte wheel and a
  24,355-byte sdist. Their inventories contain only the V3 package, license,
  readmes and distribution metadata, with no V2 runtime, tests or scripts.
- The wheel installed into a fresh virtual environment and completed setup ->
  remember -> recall -> module list/enable -> UTF-8 MCP proposal -> review list
  -> status from outside the checkout. Its import path was the isolated
  environment, not the source tree.
- SHA-256: wheel
  `38ebe6d3aa88f17993c7f4577c6688bf5f7d027135409dd1fabbccf4c80d71a5`;
  sdist `960b383799c5875ce422ed5b22f71aaf1a29be0b8697caea45b8cfc321cf4f2d`.
- Independent exact post-fix product and security rereads both returned READY
  with no reproducible blocker and no P0-P3 security finding.

## Next

The excluded V2 tree remains physically present but inert because the host
blocked a broad destructive cleanup without a new explicit approval. Obtain the
hosted four-job CI result on the alpha PR before considering merge. Physical
deletion is a separate one-time cleanup. Merge, tag and package publication
remain explicit gates.
