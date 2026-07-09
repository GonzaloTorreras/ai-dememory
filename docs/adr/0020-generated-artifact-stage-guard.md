# ADR 0020: Generated Artifact Stage Guard

## Status

Accepted for v2 draft.

## Context

The v2 release checklist states that generated SQLite databases, reports,
caches, and distilled context exports must not be staged. These files are
rebuildable from Markdown memory and local commands, so committing them would
blur the repository contract and could leak local review or session state.

Before this ADR, the invariant was documented but not executable. A maintainer
had to inspect `git status` manually before release.

## Decision

Add `ai-dememory artifact-guard`, backed by `scripts/artifact_guard.py`, and
make `ai-dememory release-check` and CI run it.

The guard inspects `git diff --cached --name-only` and fails when staged paths
match generated or disposable artifact classes:

- root generated directories: `indexes/`, `reports/`, `distilled/`, `build/`,
  and `dist/`
- cache directories such as `__pycache__/`, `.pytest_cache/`, and `.mypy_cache/`
- Python package metadata directories ending in `.egg-info`
- generated database and bytecode suffixes such as `.sqlite`, `.sqlite-wal`,
  `.sqlite-shm`, `.db`, `.pyc`, and `.pyo`

The check is intentionally staged-file only. Local generated files may exist
after smoke tests, but release readiness fails only if those files are selected
for commit.

## Benefits

- Converts a release checklist invariant into an automated gate.
- Makes CI workflow drift visible through the existing `ci-guard`.
- Protects private/local generated reports and context exports from accidental
  inclusion.
- Keeps Markdown memory and reviewed inbox artifacts as the canonical commit
  surface.
- Avoids blocking normal smoke commands that create disposable local artifacts.

## Limitations

- The guard is path-based and does not inspect file contents.
- It only checks staged files, not untracked generated files.
- Nonstandard generated paths must be added explicitly if future commands create
  them outside the current conventions.

## Future Risks

- If the project starts publishing checked-in generated reference fixtures,
  those paths need an allowlist.
- If release automation runs outside a Git checkout, this check will report a
  Git inspection failure.
