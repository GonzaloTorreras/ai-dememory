# ADR 0240: Publish Plan Workflow URL

## Status

Accepted for offline URL resolution. ADR 0255 superseded the publication
interpretation on 2026-07-26: the resolved `publish.yml` URL now identifies a
read-only hosted preflight, not a publisher.

## Context

`ai-dememory publish-plan` reports the legacy hosted-preflight path and inputs
for evaluating TestPyPI or PyPI readiness. Before this change, the
`workflow_url` field always used `https://github.com/<owner>/<repo>/...`, even
when the command was running inside the distribution checkout with a GitHub
remote configured.

Maintainers need a concrete preflight URL in release handoffs, but planning
must remain offline and must not call GitHub APIs or dispatch the workflow.

## Decision

Resolve `workflow_url` from `[project.urls].Repository` in `pyproject.toml`
first, then from the local `origin` git remote when either value points at
GitHub.

Supported remote forms include:

- `https://github.com/<owner>/<repo>.git`
- `git@github.com:<owner>/<repo>.git`
- `ssh://git@github.com/<owner>/<repo>.git`

If project metadata is unavailable, git is unavailable, the root is not a git
checkout, or the remote is not a GitHub remote, `publish-plan` keeps the
documented placeholder:

```text
https://github.com/<owner>/<repo>/actions/workflows/publish.yml
```

The command remains read-only. It does not contact GitHub, inspect workflow
runs, dispatch workflows, publish packages, write files, or record evidence.

## Consequences

- Distribution checkouts show a directly usable hosted-preflight URL.
- Plain vaults and non-GitHub forks keep deterministic fallback output.
- MCP `memory.publish_plan` and release-evidence handoff commands benefit from
  the same resolved URL because they reuse the CLI publish-plan payload.

## Limitations

- The URL is derived from local project metadata or git remote configuration
  and may be stale if either value is stale.
- The URL does not prove the workflow exists on GitHub or that canonical
  release environments and Trusted Publisher identities are configured.
- Only GitHub remotes are resolved; other forge URLs keep the placeholder.

## Future Work

- Add connector-backed workflow existence checks only if release dashboards need
  live GitHub metadata.
- Include latest workflow run URLs only after readiness evidence is reviewed
  and recorded.
- Add explicit remote selection only if maintainers use a non-`origin` release
  remote.

## Dependencies

- ADR 0236 defines CLI publish planning.
- ADR 0237 defines MCP publish planning.
- ADR 0239 adds publish-plan commands to release evidence handoffs.
- `scripts/publish_plan.py` owns publish-plan payload construction.

## References

- `scripts/publish_plan.py`
- `tests/test_memory_tools.py`
- `docs/release-v2-checklist.md`
