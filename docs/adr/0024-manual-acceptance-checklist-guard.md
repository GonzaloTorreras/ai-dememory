# ADR 0024: Manual Acceptance Checklist Guard

## Status

Accepted for v2 draft.

## Context

Manual release acceptance is intentionally separate from automated gates. The
canonical acceptance item registry lives in `scripts/manual_acceptance.py` so
`ai-dememory acceptance record`, `acceptance status`, and `release-evidence`
can agree on item ids and descriptions.

The release checklist also contains a Manual Acceptance section for reviewers,
but that section had drifted from the registry: descriptions differed, and some
registry items were not represented exactly. That could cause reviewers to
record evidence under the wrong item or miss an expected manual proof.

## Decision

Add `ai-dememory acceptance-guard`, backed by `scripts/acceptance_guard.py`,
and make `release-check` and CI run it.

The guard checks `docs/release-v2-checklist.md` to ensure the Manual Acceptance
section contains every `ACCEPTANCE_ITEMS` id and canonical description, plus the
`ai-dememory acceptance record --item <item-id>` command shape.

## Benefits

- Keeps reviewer-facing manual acceptance instructions aligned with the
  evidence registry used by `release-evidence`.
- Prevents checklist drift when acceptance items are added or renamed.
- Makes manual acceptance gaps visible in CI and local release checks.
- Keeps human approval explicit while improving the automation around evidence
  collection.

## Limitations

- This guard checks documentation alignment, not whether manual acceptance has
  actually been completed.
- It is text-based and expects canonical descriptions to appear in the release
  checklist.
- Manual acceptance still requires a reviewer to run the real client, provider,
  maintenance, and TestPyPI checks.

## Future Risks

- If manual acceptance moves to a generated checklist, the guard should validate
  the generator input instead.
- If item descriptions become long or provider-specific, exact text matching may
  become brittle.
- If acceptance evidence needs stronger identity guarantees, a future ADR should
  cover reviewer identity and artifact provenance.
