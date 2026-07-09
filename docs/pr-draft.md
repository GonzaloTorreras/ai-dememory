# Draft PR Handoff

Use this runbook when opening a draft pull request for a v2 change. Keep it
generic: do not hard-code an old pull request number, old title, or completed
review state.

## Required Fields

- Draft PR URL: `https://github.com/GonzaloTorreras/ai-dememory/pull/<number>`
- Branch: `<branch-name>`
- Base branch: `<base-branch>`
- Stacked on: `<parent PR or branch>`
- Draft PR title: `<short title>`
- Current status: `Draft PR`
- Merge policy: `Do not merge without explicit user approval.`

## Body Template

```markdown
## Summary

- <short summary>

## Tests

- `python3 scripts/ai_dememory.py pr-draft-guard`
- `python3 scripts/ai_dememory.py pr-template-guard`
- `python3 scripts/ai_dememory.py ci-guard`
- `python3 scripts/ai_dememory.py release-checklist-guard`
- `python3 scripts/ai_dememory.py adr-guard`
- `python3 scripts/ai_dememory.py release-check`
- `python3 scripts/ai_dememory.py validate`
- `python3 scripts/ai_dememory.py secret-scan`
- `python3 scripts/ai_dememory.py eval-recall`
- `python3 -m unittest discover -s tests`
- `python3 -m compileall -q scripts mcp/server ai_dememory_tool`

## Notes

- Stacked on: `<parent PR or branch>`.
- Draft PR: keep this PR in draft until CI and any required manual evidence are
  reviewed.
- Do not merge or publish without explicit approval.
```

## Validation Commands

After the draft PR exists, set the PR URL before PR-gated runtime checks:

```bash
export AI_DEMEMORY_PR_URL="https://github.com/GonzaloTorreras/ai-dememory/pull/<number>"
python3 scripts/ai_dememory.py release-check --strict
python3 scripts/ai_dememory.py mcp-smoke
```

Windows PowerShell equivalent:

```powershell
$env:AI_DEMEMORY_PR_URL = "https://github.com/GonzaloTorreras/ai-dememory/pull/<number>"
py -3 scripts\ai_dememory.py release-check --strict
py -3 scripts\ai_dememory.py mcp-smoke
```

## Safety Notes

- Keep the pull request as a draft until the user explicitly asks to publish it
  as ready for review.
- Do not merge, publish packages, deploy, rotate secrets, or force-push without
  explicit user approval.
- Do not stage generated SQLite indexes, reports, caches, distilled context
  exports, or package build outputs unless the change explicitly reviews them.
- Treat durable memory edits as human-reviewed changes.

## After The Draft PR Exists

1. Add the draft PR URL to the local evidence notes or final response.
2. Run `AI_DEMEMORY_PR_URL`-gated checks if the PR scope changes MCP runtime
   behavior.
3. Keep stacked PRs based on their immediate parent branch until the stack is
   merged or rebased intentionally.
4. Record any skipped checks and the reason in the PR body.
