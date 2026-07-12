# ADR 0250: Prompt-Aware Recall and Reviewed Onboarding

## Status

Accepted.

## Context

ai-dememory already exposes search, bounded context, hooks, setup planning, and
review-first proposals. Those surfaces still require an agent or user to decide
when to recall. The existing hook command captures event metadata and can emit
free-form output, but it does not derive context from the submitted prompt and
active project. New vaults also begin without personal values, working
preferences, agent recommendations, or project aliases.

Codex and Claude Code `UserPromptSubmit` hooks both accept JSON on stdin and can
add hook-provided context to the next model request. Codex Stop hooks require
JSON output, so capture receipts and harness protocol output must remain
separate.

## Decision

Add three coordinated, local-first capabilities:

1. `turn_context.build_turn_context` derives deterministic keywords and an
   active-project hint from the prompt and `cwd`, then retrieves bounded,
   explainable public/internal reviewed active memory. Ranked items inject only
   above a configurable relevance threshold; the separately bounded baseline
   is limited to reviewed `onboarding`/`baseline` durable entries.
2. `hook-event dispatch` adapts the turn-context result to JSON lifecycle-hook
   output. Metadata capture remains a best-effort side effect. Stop learning is
   opt-in, accepts only explicit learning signals, secret-scans them, and writes
   deduplicated proposals to `inbox/llm-captures/`.
3. `ai-dememory onboard` previews a minimum reviewed baseline and applies it
   only with reviewer identity, `--apply`, and the reviewed preview fingerprint.
   Canonical-memory conflicts stop the entire apply; every output is staged
   before a rollback-capable batch commit. An incomplete rollback is surfaced
   as a recovery error and preserves backup evidence for manual restoration.

The distributed skill and managed instruction block require recall before
non-trivial project work when prior context can materially change the result.
They remain advisory fallbacks when a native hook is unavailable or untrusted.

## Consequences

- Relevant project memory can reach Codex, Claude Code, or a generic JSON
  wrapper before each meaningful prompt without relying on MCP tool choice.
- Trivial prompts, missing indexes, invalid payloads, suspected secrets, and
  weak matches add no context and do not block the turn.
- Reviewed values and recommendations are available early in a new vault.
- Automatic learning creates review work, not durable facts.
- Project matching and baseline selection are visible in ranking evidence.

## Limitations

- Hooks must be enabled and trusted, and the hook process must be able to locate
  the vault through its root argument or `AI_DEMEMORY_ROOT`.
- Deterministic FTS and exact tokenized project matching do not provide fuzzy or
  embedding-based semantic retrieval.
- Stop learning depends on explicit structured signals or
  `[ai-dememory-learning]` markers; raw transcripts are intentionally ignored.
- A skill or instruction file cannot mechanically enforce recall in a harness
  without compatible lifecycle hooks.

## Future Work

- Add measured recall fixtures for cross-project ambiguity and multilingual
  aliases before changing the relevance threshold.
- Add native adapters for more harnesses only when their lifecycle contracts are
  documented and testable.
- Consider lifecycle usage receipts after their privacy and write-amplification
  costs have been evaluated.

## Dependencies

- ADR 0059 defines explainable search ranking.
- ADR 0063 defines MCP auto context from generated working memory.
- ADR 0079 defines passive local setup planning.
- ADR 0005 and ADR 0006 define provider hook and managed instruction bounds.
- `scripts/turn_context.py`, `scripts/harness_hooks.py`, and
  `scripts/onboarding.py` implement this decision.
