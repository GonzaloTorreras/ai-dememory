# ADR 0107: CI PR-Gated MCP Runtime Smoke

## Status

Accepted.

## Context

`ai-dememory mcp-smoke` exercises the live stdio MCP server against a
temporary fixture vault and requires `AI_DEMEMORY_PR_URL` unless explicitly
bypassed for local debugging. The PR URL gate prevents maintainers from treating
runtime smoke output as release evidence before a pull request exists.

Before this decision, CI ran static MCP contract checks, package install smoke,
Docker MCP smoke, and non-strict release checks, but it did not run the
PR-gated strict release check or the PR-gated runtime smoke. Maintainers still
had to run those gates locally after opening a draft PR. That left a workflow
gap where CI could pass while PR-gated release evidence or the richer MCP
runtime fixture set was broken.

## Decision

Run these commands in the CI verification workflow for pull request events only:

- `python scripts/ai_dememory.py release-check --strict`
- `python scripts/ai_dememory.py mcp-smoke`

Both CI steps set:

```yaml
AI_DEMEMORY_PR_URL: ${{ github.event.pull_request.html_url }}
```

The ordinary `release-check` still runs early and non-strict so CI can report
repository readiness before generated indexes exist. The strict release check
and MCP runtime smoke run later, after index/search/recall smoke and before
package install, package build, and Docker smokes. This lets strict
`release-check` see the generated SQLite index that `doctor` expects while
keeping package validation after the PR-gated release/runtime gates.

Pushes to `main` keep the non-PR release-check behavior because no pull request
URL is available in that event.

Strengthen `scripts/ci_guard.py` so local release checks fail if the workflow
loses either PR-gated step, runs them without the pull-request condition, omits
`AI_DEMEMORY_PR_URL`, or moves them away from the post-index, pre-install-smoke
boundary.

## Benefits

- Makes GitHub PR checks exercise the same MCP runtime contract that reviewers
  already run locally.
- Makes GitHub PR checks exercise the strict release-check path with a real PR
  URL.
- Removes a manual-only gap from the automated PR validation path.
- Preserves the PR URL gate instead of weakening runtime smoke for CI.
- Keeps push-to-main CI compatible with events that do not have a pull request
  URL.

## Limitations

- The CI step still uses the repository's fixture vault, not a real GUI MCP
  client. Real client checks remain manual acceptance.
- The smoke adds runtime cost to pull request CI.
- Push-to-main CI does not run strict release-check or `mcp-smoke` because no PR
  URL exists.
- Strict release-check depends on the earlier CI `index` smoke to satisfy the
  doctor index check.

## Future Risks

- If the runtime smoke becomes too slow, CI may need a smaller PR fixture set
  and a fuller scheduled workflow.
- If GitHub changes pull request payload names, the environment expression must
  be updated.
- If release evidence starts consuming external CI status, this PR-only smoke
  should become part of that external evidence model.

## Dependencies

- ADR 0019 defines the CI workflow guard.
- ADR 0021 defines the expanded MCP runtime smoke.
- ADR 0093 defines the initialized notification runtime smoke behavior.
- ADR 0095 defines runtime response-id matching behavior.
- `.github/workflows/ci.yml` remains the GitHub Actions verification workflow.
- `scripts/mcp_runtime_smoke.py` remains the executable runtime smoke.
- `scripts/ci_guard.py` remains the executable CI workflow contract.
