# ADR 0161: Review Policy Defaults In Mode And Plan Output

Status: Accepted

## Context

The v2 configuration direction includes explicit false-positive and conflict
review policy fields such as `triage_policy`, `resolution_policy`,
`scan_on_validate`, and LLM auto-deny categories. Review modes already describe
LLM capability boundaries, but new vault templates did not expose every policy
knob and `review modes` / `review plan` did not return the normalized policy
values.

That made MCP clients and humans infer review guardrails from docs instead of
reading the active vault configuration.

## Decision

Add policy defaults to both vault templates:

```toml
[false_positives]
enabled = true
triage_policy = "human_only"

[conflicts]
enabled = true
scan_on_validate = true
scan_on_consolidate = true
resolution_policy = "human_only"
llm_preselect_min_confidence = 0.85
human_required_severities = ["high", "critical"]
llm_auto_deny_categories = ["restricted", "durable", "policy"]
```

Normalize these values through `review_policy_config()`, then include the
result in CLI and MCP `review modes` and `review plan` output.

This slice does not make LLM-assisted cleanup autonomous. The policy fields are
reported as review guidance and future enforcement inputs. Existing durable and
canonical memory write gates still apply.

## Benefits

- New vaults show the intended human/LLM review policy surface explicitly.
- MCP clients can display the same active guardrails as the CLI.
- Invalid policy values fail early when review policy is inspected.
- Review plans now explain both the active mode and configured policy.

## Limitations

- `enabled=false`, `scan_on_validate`, and `scan_on_consolidate` are not yet
  enforced by validation or consolidation workflows.
- LLM preselection thresholds and auto-deny categories are guidance only until
  LLM-assisted cleanup is implemented.
- Policy names remain stable strings; custom policies are not supported.

## Future Work

- Enforce `scan_on_validate` and `scan_on_consolidate` when those workflows
  start invoking conflict review automatically.
- Use `resolution_policy`, `llm_preselect_min_confidence`, and deny categories
  when adding LLM recommendation artifacts.
- Add a dedicated policy status command if review configuration grows beyond
  mode and plan output.

## Dependencies

- ADR 0002 defines configurable review modes.
- ADR 0027 defines canonical review mode names.
- ADR 0082 exposes MCP review mode configuration.
- ADR 0157 defines expanded conflict categories.
- ADR 0160 defines configured review state paths.
- `scripts/review_memory.py` owns review mode, plan, and policy output.
