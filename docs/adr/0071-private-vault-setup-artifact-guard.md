# ADR 0071: Private Vault Setup Artifact Guard

Status: Accepted for the v2 draft.

## Context

The distribution repo and user vault repos have different roles. The tool repo
ships code, docs, templates, and release automation. User vault repos contain
private Markdown memory plus local generated state that can be rebuilt.

The vault template already ignores generated SQLite indexes, context exports,
and reports while allowing placeholder README files. However,
`docs/create-memory-repo.md` still showed a `git add` command that staged whole
`distilled/`, `indexes/`, and `reports/` directories. That contradicted the
same guide's "do not commit" section and weakened the private-vault setup UX.

## Decision

Add `ai-dememory vault-setup-guard`, backed by `scripts/vault_setup_guard.py`.

The guard validates that:

- `docs/create-memory-repo.md` does not tell users to `git add` whole generated
  directories
- the guide stages only generated-directory placeholder README files
- `vault-template/.gitignore` and the packaged vault `.gitignore` ignore
  generated index, report, and distilled outputs while allowing placeholder
  READMEs

The CLI path in the guide now stages canonical setup files, memory directories,
working-state placeholders, and explicit placeholder README files for generated
directories.

## Benefits

- Removes contradictory setup guidance for private memory repos.
- Makes generated-artifact safety part of `release-check`, not only prose.
- Keeps GitHub template and CLI-created vault setup aligned with the same
  `.gitignore` contract.
- Reduces the chance that users commit local generated reports, indexes, or
  context exports into private vault history.

## Caveats

- The guard validates documented setup commands and `.gitignore` patterns; it
  cannot control arbitrary user Git commands after setup.
- Placeholder README files under generated directories remain committed so fresh
  vaults explain where generated artifacts will appear.
- The guard is path-pattern based and does not inspect generated file content.

## Future Risks

- If generated artifact directories change, both the guard and vault template
  `.gitignore` patterns must be updated together.
- If a future release intentionally commits generated reference artifacts, those
  paths will need an explicit allowlist.
- If setup docs become generated, this guard should validate the generated
  source instead of the rendered Markdown.

## Dependencies

- ADR 0020 defines generated artifact staging boundaries.
- ADR 0011 defines reusable install smoke and vault template release coverage.
- `scripts/artifact_guard.py` remains the staged-file release guard.
- `vault-template/.gitignore` and
  `ai_dememory_tool/templates/vault/.gitignore` remain mirrored by the vault
  template release check.
