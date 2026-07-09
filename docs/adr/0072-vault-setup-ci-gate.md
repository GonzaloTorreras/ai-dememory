# ADR 0072: Vault Setup CI Gate

Status: Accepted for the v2 draft.

## Context

ADR 0071 added `ai-dememory vault-setup-guard` so private vault setup docs
cannot drift back toward staging generated index, report, or distilled context
directories. The guard was wired into `release-check`, but CI and the pull
request template still listed the older guard set explicitly.

That split created a review risk: contributors could see a passing PR checklist
or CI workflow that did not name the new setup-safety gate, while local
`release-check` still depended on it. Because this guard protects the first
private-vault setup experience, it should be visible wherever v2 release gates
are enumerated.

## Decision

Promote `vault-setup-guard` to an explicit CI and PR-template gate.

The change updates:

- `.github/workflows/ci.yml` to run `python scripts/ai_dememory.py
  vault-setup-guard`
- `scripts/ci_guard.py` so CI drift is executable
- `.github/pull_request_template.md` so reviewers see the guard directly
- `scripts/pr_template_guard.py` so the template cannot omit it
- `docs/release-v2-checklist.md` so release readiness names the CI coverage

## Benefits

- Makes private vault setup safety visible in every PR validation surface.
- Keeps CI, PR template, release checklist, and `release-check` aligned.
- Catches generated-artifact setup doc regressions before merge, not only during
  local release handoff.

## Caveats

- This does not complete manual vault acceptance in Obsidian; it only checks
  documented Git setup and template ignore rules.
- CI validates repository docs and templates, not a user's private Git host
  configuration.
- The guard is fast and deterministic, but it adds another required command to
  every CI run.

## Future Risks

- If CI is split into faster and slower jobs, this guard should stay with static
  repository validation rather than package or Docker smoke.
- If private-vault setup docs are generated from another source, CI should run
  the guard after generation or validate the source directly.
- If multiple vault templates are added, the guard and CI command may need a
  template selector.

## Dependencies

- ADR 0020 defines generated artifact staging boundaries.
- ADR 0071 defines the private vault setup artifact guard.
- `scripts/ci_guard.py` remains the executable CI workflow contract.
- `scripts/pr_template_guard.py` remains the executable PR checklist contract.
