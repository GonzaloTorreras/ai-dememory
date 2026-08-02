---
name: memory-setup
description: Set up ai-dememory for a local vault, MCP, bounded hooks, provider imports, or reviewed maintenance schedules. Use when the user asks to install, configure, run the initial wizard, choose resource intensity, or enable autonomous local upkeep.
---

# Memory Setup

Use the installed `ai-dememory` CLI as the source of truth. Package and plugin
installation are passive: they do not install hooks, start jobs, read provider
files, or promote memory.

## First Run

1. Run `ai-dememory setup plan --json`.
2. Preview the baseline with:
   `ai-dememory setup wizard --intensity <minimal|balanced|active> --model-policy <off|advisory|proposals> --json`.
3. Inspect `resource_policy`, `integrations`, every planned write, and
   `plan_sha256`. Reject secret or personal content that should not become
   reviewed vault memory.
4. Apply only the exact reviewed preview with its emitted command:
   `ai-dememory setup wizard ... --apply --expect-plan-sha256 <sha> --json`.
5. Run `ai-dememory doctor`, `ai-dememory index`, and
   `ai-dememory setup health --json`.

Prefer `balanced` unless the user or host constraints justify another profile:

- `minimal`: manual per-turn recall, one weekly job, 5 import candidates/run,
  32 KiB/file, 256 MiB Docker ceiling.
- `balanced`: at most 1200 recall tokens/eligible turn, daily plus weekly jobs,
  20 candidates/run, 64 KiB/file, 512 MiB Docker ceiling.
- `active`: at most 2400 recall tokens/eligible turn, daily plus weekly jobs,
  working MCP profile, 50 candidates/run, 128 KiB/file, 1 GiB Docker ceiling.

All profiles make zero runtime model and embedding calls. `advisory` and
`proposals` describe what the already active host agent may do; only
`proposals` permits review-inbox session proposals. No mode auto-promotes
durable memory.

## Integrations

- Copy only the wizard-generated, absolute-vault-bound MCP config for the
  selected client. Generated servers enforce `core` by default and fail closed
  without `AI_DEMEMORY_ROOT` or `--root`.
- Generate hooks with
  `ai-dememory hooks config --client <codex|claude> --root <vault>`.
  Hook recall is public-only by default and capture metadata is off unless the
  chosen profile enables it. Preview managed instruction changes with
  `hooks install --dry-run`.
- Inspect providers with `providers detect` and `providers plan --json`.
  Preview configuration and import before either write:
  `providers configure <provider> --path <path> --dry-run --json`, then
  `import-chats <provider> --dry-run --json`.
- For a schedule, run
  `ai-dememory schedule plan --intensity <profile> --json`. Execute only the
  returned fingerprint-bound `apply_command`. Names are vault-specific; Docker
  jobs are network-disabled and resource-capped. Run
  `ai-dememory schedule status`, then confirm `setup health` reports a valid
  receipt and verified host state.

Do not edit client config, install hooks, or mutate the OS scheduler unless the
user explicitly requested that external change. Do not retry a failed apply
automatically; inspect the returned rollback state and generate a fresh plan.
