# Create A Memory Repo

User memory belongs in a private vault repository, not in the tool distribution
repo.

## CLI Path

```bash
ai-dememory init ~/code/my-memory
cd ~/code/my-memory
git init
git add README.md .ai-dememory.toml .ai-dememory-ignore.toml .gitignore memories inbox templates quality working
git add distilled/README.md indexes/README.md reports/README.md
git commit -m "Create memory vault"
```

Private vault setup does not stage generated artifact directories. The
placeholder README files keep `distilled/`, `indexes/`, and `reports/` visible
in a fresh repository; generated SQLite databases, context exports, and reports
stay ignored by `.gitignore`.

Create a private GitHub repository, then push:

```bash
git remote add origin git@github.com:<user>/<repo>.git
git branch -M main
git push -u origin main
```

Run:

```bash
ai-dememory vault-setup-guard
ai-dememory doctor
ai-dememory validate
ai-dememory secret-scan
ai-dememory index
```

## GitHub Template Path

For users who prefer GitHub UI setup:

1. Export the packaged vault template into a separate checkout:

   ```bash
   ai-dememory vault-template export ~/code/ai-dememory-vault-template
   ```

2. Review the exported files, especially `.gitignore` and
   `.ai-dememory.toml`.
3. Create a separate private `ai-dememory-vault-template` repository.
4. Push the exported files to that repository.
5. Mark the repository as a GitHub template.
6. Users click "Use this template".
7. Users create a private repository from the template.
8. Users clone their private repo and install the tool with `pipx`.

The export command copies the same template used by `ai-dememory init`. It
does not create a GitHub repository, push commits, mark a repository as a
template, or install the tool.

## What To Commit

Commit:

- Markdown memory files under `memories/`.
- Unreviewed proposals under `inbox/` only when safe and intentional.
- Template files and vault docs.

Do not commit:

- SQLite files under `indexes/`.
- Generated context under `distilled/`.
- Generated reports under `reports/`.
- `.env` files, tokens, private keys, service-account JSON, cookies, or other
  secrets.

## MCP Setup

Generate client config from inside the vault:

```bash
ai-dememory mcp-config --client codex
```

Use the generated `AI_DEMEMORY_ROOT` path so the MCP server reads the user's
vault even though the tool itself is installed globally.
