# ADR 0073: Vault Template Export Command

Status: Accepted for the v2 draft.

## Context

The distribution plan separates the `ai-dememory` tool repository from private
user memory vault repositories. `ai-dememory init` already creates a local
vault from the packaged template, and `vault-template/` mirrors the packaged
template for repository review.

The GitHub template setup path still required users to clone or browse the tool
repository and manually copy `vault-template/` into another repository. That is
easy to explain, but it is also easy to perform inconsistently, especially for
hidden files such as `.ai-dememory.toml` and `.gitignore`.

## Decision

Add `ai-dememory vault-template export <path>` as a CLI command that copies the
packaged vault template into a target directory for a separate GitHub template
repository checkout.

The command:

- uses the same packaged template source as `ai-dememory init`
- copies hidden vault configuration files
- refuses to write into a non-empty target unless `--force` is provided
- supports `--json` for setup automation and documentation tests
- prints explicit next steps for reviewing files and creating a separate
  private GitHub template repository

The command does not create a GitHub repository, push commits, mark a repository
as a template, install scheduler jobs, or install the MCP server.

## Benefits

- Gives users a direct installed-package path for creating a reusable vault
  template repository.
- Keeps private vault setup independent from forking the tool distribution repo.
- Reduces drift between `ai-dememory init`, the packaged template, and
  `vault-template/`.
- Makes hidden template files harder to omit during GitHub UI setup.

## Caveats

- GitHub repository creation and the "Template repository" setting remain
  manual because they require account-specific review and permissions.
- The export is only a file-copy operation; users still need to review and push
  the resulting repository.
- `--force` can overwrite files in the target checkout, so users should use it
  only after reviewing local changes.

## Future Risks

- If multiple vault templates are added, the command will need an explicit
  template selector and documentation for choosing among them.
- If GitHub exposes a safer template-repository API path for this workflow, the
  CLI may need an optional integration, but it should remain opt-in.
- If packaged templates gain binary assets, the current text-heavy verification
  assumptions in tests and release checks may need to change.

## Dependencies

- ADR 0071 defines private vault setup artifact boundaries.
- ADR 0072 keeps vault setup guards visible in CI and PR review.
- `ai_dememory_tool/cli.py` remains the installed-package entry point for
  vault initialization and template export.
- `vault-template/` and `ai_dememory_tool/templates/vault/` must continue to
  match.
