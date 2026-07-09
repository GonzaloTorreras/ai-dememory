# Git Lesson Capture

`ai-dememory` can scan recent git history and write review candidates for
project lessons. It does not edit canonical memory.

Generated candidates land under:

```text
inbox/git-lessons/
```

Review each candidate before promoting a stable project memory.

## Commands

Preview the current git repository:

```bash
ai-dememory learn --git --days 7 --repo .
```

Preview several repositories:

```bash
ai-dememory learn --git --days 30 --repos ~/code/app,~/code/api
```

Emit the preview as JSON:

```bash
ai-dememory learn --git --days 7 --repo . --dry-run --json
```

Write reviewed candidates after inspecting the preview:

```bash
ai-dememory learn --git --days 7 --repo . --write
```

MCP clients can preview the same candidates with `memory.git_lessons`. The MCP
tool defaults to `dry_run=true`; set `dry_run=false` only after review when you
want candidates written to `inbox/git-lessons/`.

Git lesson capture is idempotent for the same repository path, short commit SHA,
and subject. Repeat runs skip matching existing candidates with reason
`already captured`.

## Detection

The first v2 implementation scans recent commit subjects and bodies for these
lesson categories:

- `fix`
- `bug`
- `revert`
- `hotfix`
- `migration`
- `ci`
- `build`
- `auth`
- `deploy`
- `regression`

Matching commits become proposed project memories with the repository path,
commit SHA, commit date, subject, optional body excerpt, and detected
categories.

## Safety

Rendered candidates are secret-scanned before writing. If a commit message or
body contains secret-like content, the candidate is skipped.

The CLI previews by default; writing requires `--write`. The CLI command and
MCP `memory.git_lessons` tool write only to `inbox/git-lessons/`, reject
symlinked inbox paths, and never rewrite durable, project, tool, or active
memories directly.

## Limitations

This is a heuristic capture pass. It does not inspect diffs, infer root cause,
or deduplicate lessons across repositories yet. Its duplicate check is scoped
to candidates already present in `inbox/git-lessons/` for the same repository
path, short SHA, and subject. Treat generated candidates as prompts for human
review, not as accepted memory.
