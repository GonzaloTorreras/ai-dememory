---
name: memory-setup
description: Set up ai-dememory for a local vault, MCP, bounded hooks, provider imports, or reviewed maintenance schedules. Use when the user asks to install, configure, run the initial wizard, choose resource intensity, or enable autonomous local upkeep.
---

# Memory Setup

Use the installed `ai-dememory` CLI as the source of truth. Package and plugin
installation are passive: they do not install hooks, start jobs, read provider
files, or promote memory.

## First Run

1. The source tree is preparing 2.1.1, but 2.1.0 is the currently published
   compatibility route until tag-bound PyPI publication and external readback
   complete. Install `pipx install ai-dememory==2.1.0`, then for a
   human-guided first run launch
   `ai-dememory init ~/code/my-memory --wizard --require-version 2.1.0`.
   The wizard creates the vault, previews the available intensity and
   model-policy choices, and records only the selected vault-local policy. Do
   not substitute the pending source version or remove the legacy gate while
   this release state is pending.
2. Inspect the printed `resource_policy`, integrations, `.ai-dememory.toml`
   write, and `plan_sha256`. Confirm only after that preview; the wizard applies
   the exact same in-memory operating policy and fingerprint without asking for
   it again. It never creates personal memory.
3. If the user explicitly wants reviewed personal or project memory, use the
   separate `ai-dememory --root <vault> onboard` preview. Setup and onboarding
   each require that explicit root (or `AI_DEMEMORY_ROOT`) and keep the two-step
   JSON/stdin/input-file/dry-run contract: preview first, then apply the same
   input with `--apply --expect-plan-sha256 <sha> --json`.
4. Run `ai-dememory --root <vault> index` after reviewed notes exist.
   `ai-dememory --root <vault> doctor` and `ai-dememory --root <vault> setup
   health --json` are optional diagnostics, not first-run gates.

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

- Generate and inspect an absolute-vault-bound MCP config only if the selected
  client needs it: `ai-dememory --root ~/code/my-memory mcp-config --client codex`.
  Generated servers enforce `core` by default and fail closed without
  `AI_DEMEMORY_ROOT` or `--root`.
- Generate hooks with
  `ai-dememory hooks config --client <codex|claude> --root <vault>`.
  Hook recall is public-only by default and capture metadata is off unless the
  chosen profile enables it. Preview managed instruction changes with
  `ai-dememory hooks install --root <vault> --dry-run`.
- Inspect providers with `ai-dememory providers detect` (a rootless,
  read-only local diagnostic) and
  `ai-dememory --root <vault-path> providers plan --json`.
  Preview configuration and import before either write:
  `ai-dememory --root <vault-path> providers configure <provider> --path <path> --dry-run --json`, then
  `ai-dememory --root <vault-path> import-chats <provider> --dry-run --json`.
- For a schedule, run
  `ai-dememory schedule plan --intensity <profile> --json`. Execute only the
  returned fingerprint-bound `apply_command`. Names are vault-specific; Docker
  jobs are network-disabled and resource-capped. Run
  `ai-dememory schedule status`, then confirm `setup health` reports a valid
  receipt and verified host state.

Do not edit client config, install hooks, or mutate the OS scheduler unless the
user explicitly requested that external change. Do not retry a failed apply
automatically; inspect the returned rollback state and generate a fresh plan.
