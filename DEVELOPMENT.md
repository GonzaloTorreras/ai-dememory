# Development

ai DeMemory V3 is a clean product reset. The goal is useful local memory with a
small core and genuinely optional integrations, not preservation of the 2.x
toolbox.

## Authority

When sources disagree, use this order:

1. `AGENTS.md` for repository, safety and release boundaries.
2. Shipped code plus `tests_v3/` for actual behavior.
3. `docs/roadmap.md` for Now / Next / Later priorities.
4. `docs/development-status.md` for the current branch handoff.

The old task DAG, ADR collection, V2 roadmaps and research appendices are
historical input only. They are not executable backlogs and no work needs a
legacy task ID.

## Non-negotiable product rules

- No V2 migration, aliases, schema reader or compatibility tests.
- Fewer than ten public top-level commands and no maintainer commands in the
  installed CLI.
- A default installation starts zero persistent processes and makes zero model
  or network calls.
- A disabled module contributes zero runtime imports, tools and processes;
  dependencies of an installed third-party distribution remain on disk.
- Markdown is canonical; SQLite is generated and disposable.
- Direct human CLI actions may write canonical memory. Modules use the
  read/proposal-only `CoreServices` API.
- Community Python modules are trusted installed code, not sandboxes. Do not
  claim their manifest budgets are OS-enforced.

## Routine validation

Prove the smallest changed slice first:

```bash
python -m unittest tests_v3.test_save_mvp
python -m unittest tests_v3.test_recall_mvp
python -m unittest tests_v3.test_review_mvp
python -m unittest tests_v3.test_mcp_mvp
python -m unittest tests_v3.test_status_mvp
python -m unittest tests_v3.test_module_mvp
```

Only after it passes, run the wider regression checks:

```bash
python -m compileall -q src/ai_dememory
python -m unittest discover -s tests_v3 -t .
python -m pip install .
ai-dememory setup <temporary-vault> --yes
ai-dememory remember "smoke memory"
ai-dememory recall smoke
ai-dememory status --json
```

CI runs the same product tests on Windows, macOS and Linux with Python
3.11-3.13. Package publishing remains a separate explicit gate.

## Delivery shape

Prefer one vertical, user-visible slice over horizontal frameworks. A PR should
state its outcome, affected paths, tests, residual risk and rollback. A fresh
read-only review is required before merge. Do not add a new ADR, guard, task ID
or compatibility branch unless a demonstrated irreversible decision needs it.
