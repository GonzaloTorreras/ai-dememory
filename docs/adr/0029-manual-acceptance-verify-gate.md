# ADR 0029: Manual Acceptance Verify Gate

## Status

Accepted for v2 draft.

## Context

Manual release acceptance is intentionally separate from automated release
checks. `ai-dememory acceptance status` shows recorded evidence, and
`release-evidence` reports completed, blocked, and remaining items. Before this
ADR, there was no direct command that returned a failing exit code until every
manual acceptance item had reviewed passing evidence.

Reviewers need a final local gate for the moment when a draft PR is ready to
move from automated readiness into human acceptance completion.

## Decision

Add `ai-dememory acceptance verify`.

The command is read-only. It loads manual acceptance evidence from
`inbox/release-acceptance/`, reports completed, blocked, and remaining items,
and exits:

- `0` when every canonical acceptance item has at least one reviewed `passed`
  record.
- `1` when any acceptance item is missing or only has blocked evidence.

`--json` emits a structured summary for release handoffs and scripts. Blocked
items remain incomplete until a later `passed` record exists.

## Benefits

- Gives reviewers an explicit manual acceptance completion gate.
- Keeps automated release checks separate from human acceptance.
- Makes blocked acceptance visible without treating it as success.
- Enables local scripts and PR handoffs to fail clearly when manual work
  remains.

## Limitations

- The verifier trusts reviewed acceptance records; it does not independently
  run real MCP clients, Obsidian, provider imports, or publishing.
- Evidence identity remains append-only Markdown frontmatter, not cryptographic
  attestation.
- Package install smoke can only verify the command surface because a fresh
  temporary vault intentionally lacks real manual acceptance proof.

## Future Risks

- If manual acceptance item ids change, existing records may need migration.
- If release automation consumes this gate, blocked record transitions may need
  stronger status history.
- If reviewer identity requirements become stricter, the verifier should share
  the same provenance model as durable memory approval.
