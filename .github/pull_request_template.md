## Summary

-

## Validation

- [ ] `python3 scripts/ai_dememory.py doctor`
- [ ] `python3 scripts/ai_dememory.py verify-mcp`
- [ ] `python3 scripts/ai_dememory.py mcp-inventory --check-docs`
- [ ] `python3 scripts/ai_dememory.py ci-guard`
- [ ] `python3 scripts/ai_dememory.py artifact-guard`
- [ ] `python3 scripts/ai_dememory.py vault-setup-guard`
- [ ] `python3 scripts/ai_dememory.py pr-template-guard`
- [ ] `python3 scripts/ai_dememory.py pr-draft-guard`
- [ ] `python3 scripts/ai_dememory.py acceptance-guard`
- [ ] `python3 scripts/ai_dememory.py adr-guard`
- [ ] `python3 scripts/ai_dememory.py release-checklist-guard`
- [ ] `python3 scripts/ai_dememory.py release-check`
- [ ] `python3 scripts/ai_dememory.py roadmap status --json`
- [ ] `python3 scripts/ai_dememory.py api-smoke`
- [ ] `python3 scripts/ai_dememory.py validate`
- [ ] `python3 scripts/ai_dememory.py secret-scan`
- [ ] `python3 scripts/ai_dememory.py eval-recall`
- [ ] `python3 scripts/ai_dememory.py install-smoke`
- [ ] `python3 scripts/ai_dememory.py package-build-smoke`
- [ ] `python3 -m unittest discover -s tests -t .`
- [ ] `python3 -m compileall -q scripts mcp/server ai_dememory_tool`

## MCP Runtime

- [ ] PR exists before MCP runtime testing.
- [ ] `AI_DEMEMORY_PR_URL` is set to this PR.
- [ ] `python3 scripts/ai_dememory.py mcp-smoke`
- [ ] A separate disposable smoke vault was initialized with `python3 scripts/ai_dememory.py init <initialized-smoke-vault> --no-wizard`; the public checkout has no vault marker.
- [ ] `python3 scripts/ai_dememory.py --root <initialized-smoke-vault> mcp-client-smoke --command python3 --command-arg <absolute-checkout>/scripts/ai_dememory.py`
- [ ] Smoke output includes `OK ping`.
- [ ] Docker local MCP smoke passes if Docker-related files changed.
- [ ] `docs/mcp-v2-gap-analysis.md` is still accurate for any MCP protocol
  surface changed by this PR.

## Safety

- [ ] No secrets, credentials, `.env` contents, private keys, service account
  JSON, cookies, or recovery codes are added.
- [ ] No generated SQLite, reports, caches, or distilled context outputs are
  staged unless explicitly reviewed.
- [ ] Durable memory changes include human review.

## Solo-maintainer review (before merge)

- [ ] Canonical `verify` is green for the exact current base/head tuple.
- [ ] One fresh read-only subagent reviewed the exact diff and returned `READY`.
- [ ] `GonzaloTorreras` posted a `codex-solo-review` receipt naming the reviewer,
      scope, and exact CI evidence.
- [ ] The root agent re-read the tuple, threads, checks, and clean worktree and
      will merge only with `expected_head_sha`.
