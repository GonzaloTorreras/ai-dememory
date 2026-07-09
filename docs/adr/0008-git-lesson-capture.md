# ADR 0008: Git Lesson Capture As Review Candidates

## Status

Accepted for v2 draft.

## Context

The v2 roadmap calls for `ai-dememory learn --git` to capture lessons from
recent commits across one or more repositories. Commit history can reveal
fixes, regressions, migrations, CI failures, build changes, auth issues, and
deploy incidents that should become project memory after review.

Directly promoting commit-derived facts would be risky because commit messages
are terse, may contain secrets, and often need human interpretation.

## Decision

Add `scripts/git_lessons.py` and expose it as:

```bash
ai-dememory learn --git --days 7 --repo .
ai-dememory learn --git --days 30 --repos ~/code/a,~/code/b
ai-dememory learn --git --days 7 --repo . --write
```

The command reads recent `git log` output, classifies likely lesson-bearing
commits by keyword, renders proposed project memories, secret-scans the
rendered Markdown, and previews candidates by default. Writing safe candidates
to `inbox/git-lessons/` requires explicit `--write`.

Supported categories are:

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

## Benefits

- Lessons from development history enter the same review workflow as other
  memory candidates.
- No dependency beyond local `git` is required.
- Secret-like commit content is blocked before a candidate is written.
- Multi-repository scanning is available without background automation.

## Limitations

- Classification is keyword-based and may miss implicit lessons.
- The implementation reads commit subjects and bodies, not diffs.
- Candidates can duplicate existing project memories until a later
  deduplication/review pass handles them.

## Future Risks

- Commit messages may include sensitive incident details that need stronger
  provider-specific filters.
- Diff-based lesson capture could expose secrets and requires a separate safety
  design.
- High-volume repositories may need pagination, persisted cursors, and
  deduplication by commit SHA.
