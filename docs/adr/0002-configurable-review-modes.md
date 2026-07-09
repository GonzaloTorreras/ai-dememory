# ADR 0002: Configurable Review Modes

Status: Accepted

Date: 2026-06-19

## Context

The memory tool needs LLM-assisted review without letting LLMs silently mutate
durable memory. Different sessions need different levels of automation: some
require strict human-only decisions, while low-risk inbox proposal triage
benefits from LLM summaries and draft merge proposals.

## Decision

`ai-dememory` provides built-in review modes in the `[review]` section of
`.ai-dememory.toml`:

- `strict`: LLMs gather evidence only.
- `balanced`: LLMs may group low-risk findings and recommend conflict outcomes.
- `assisted`: LLMs may draft triage notes and merge proposals.
- `autonomous_proposals`: LLMs may organize low-risk public/internal inbox
  candidates, but canonical memory still requires human approval.

Legacy `batch` config values are treated as an alias for
`autonomous_proposals` so existing vaults continue to load.

The CLI exposes:

- `ai-dememory review modes`
- `ai-dememory review configure-mode --mode <mode>`
- `ai-dememory review plan --kind <kind>`

MCP initially exposed read-only `memory.review_modes` and `memory.review_plan`.
ADR 0082 later adds `memory.review_configure_mode` for reviewed local config
writes that still do not mutate canonical memory.

## Consequences

- Agents can ask for a machine-readable plan before performing review work.
- The active review policy is versioned in the vault config.
- Human approval remains required for durable memory writes in every built-in
  mode.
- `autonomous_proposals` improves throughput but deliberately disables
  automatic apply of reviewed changes to canonical memory.

## Caveats

- Modes are local policy hints and gates for tool behavior; they are not a
  substitute for human review.
- The first implementation does not support user-defined modes or per-project
  policy overrides.
- A malicious or poorly configured client can ignore the plan text, so sensitive
  data protection still depends on command-level secret scanning and MCP
  default filtering.

## Future Work

- Add custom mode definitions after the built-in modes have real usage.
- Add review-mode telemetry to maintenance reports.
- Consider mode-aware MCP write approval hints if clients expose richer
  approval UX.
