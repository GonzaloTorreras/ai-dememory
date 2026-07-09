# ADR 0074: Install Smoke Vault Template Export

Status: Accepted for the v2 draft.

## Context

ADR 0073 added `ai-dememory vault-template export <path>` so users can create
a separate private GitHub vault template repository from the installed package.
Source-checkout tests verify that the export matches `vault-template/`, but the
main distribution path is the installed console script.

Without installed-package smoke coverage, packaging drift could omit hidden
template files or break the command even while source tests pass.

## Decision

Extend package install smoke to run:

```bash
ai-dememory vault-template export <temp-template-repo> --json
```

from the fresh installed CLI environment. The smoke validates:

- the JSON `target` matches the requested export directory
- the command reports copied files
- hidden files `.ai-dememory.toml`, `.ai-dememory-ignore.toml`, and
  `.gitignore` exist in the export
- representative README files for durable memory and LLM capture inbox setup
  exist

## Benefits

- Proves the installed package ships the reusable vault template export command.
- Catches packaging mistakes around hidden files before TestPyPI or PyPI
  release.
- Keeps the GitHub template repo setup path aligned with the supported package
  install workflow.

## Limitations

- The smoke does not create a GitHub repository or mark it as a template.
- It validates representative files, not every byte of the exported tree.
  Source tests and `release-check` continue to verify full template parity.
- It runs in a temporary directory, so it does not test user-specific GitHub
  permissions or repository settings.

## Future Risks

- If multiple templates are added, install smoke should exercise the default
  template and at least one explicit selector.
- If the template gains binary files, the smoke may need file-size or checksum
  checks rather than text-oriented representative checks.
- If package data configuration changes, this smoke should remain close to the
  package install step so missing packaged files fail early.

## Dependencies

- ADR 0011 defines the reusable install smoke runner.
- ADR 0073 defines the vault template export command.
- `scripts/install_smoke.py` remains the installed package distribution smoke.
- `ai_dememory_tool/templates/vault/` remains the packaged template source.
