# ADR 0023: Pull Request Template Guard

## Status

Accepted for v2 draft.

## Context

The v2 workflow depends on reviewers running a consistent set of validation
commands before marking a pull request ready. As new gates were added for CI
drift, generated artifact staging, local REST API smoke, package install smoke,
and MCP client smoke, the pull request template could fall behind even while
the commands themselves worked.

Before this ADR, `release-check` required the PR template file to exist but did
not verify that it mentioned the current validation gates.

## Decision

Add `ai-dememory pr-template-guard`, backed by
`scripts/pr_template_guard.py`, and make `ai-dememory release-check` and CI run
it.

The guard checks `.github/pull_request_template.md` for the required sections
and validation snippets:

- static checks such as doctor, MCP verification, inventory, CI guard,
  generated artifact guard, release-check, API smoke, validation, secret scan,
  recall evaluation, install smoke, unit tests, and compileall
- PR-gated runtime checks using `AI_DEMEMORY_PR_URL`
- MCP runtime and generated client config smoke
- generated artifact staging safety text

## Benefits

- Keeps reviewer instructions aligned with the automated v2 gate set.
- Makes PR template drift visible during local release checks and CI.
- Reduces the chance of opening a draft PR without the expected evidence.
- Keeps the check dependency-free and consistent with existing text guards.

## Limitations

- The guard is text-based and requires exact command snippets.
- It cannot prove reviewers actually ran the commands.
- It does not validate GitHub checkbox state or PR comments.

## Future Risks

- If validation commands are renamed, the guard and template must change
  together.
- If the project moves to generated PR bodies, this guard may need to validate
  the generator template instead.
- A much larger PR template could become noisy; the guard should stay focused
  on release-critical gates only.
