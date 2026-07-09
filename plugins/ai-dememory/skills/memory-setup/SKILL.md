---
name: memory-setup
description: Set up ai-dememory for a local vault, MCP server use, provider imports, local hook config, or opt-in scheduler installation. Use when the user asks to install, configure, detect providers, add MCP config, configure hooks, or schedule maintenance for ai-dememory.
---

# Memory Setup

Use the installed `ai-dememory` CLI as the source of truth. Do not edit Codex
config or OS schedulers unless the user explicitly asks.

Workflow:

1. Run `ai-dememory setup plan --json` for a read-only first-run checklist.
2. Run `ai-dememory setup health --json` for combined scheduler, provider,
   artifact, generated packet archive cleanup, lock, and review status before
   applying setup changes.
3. Run `ai-dememory doctor` when a vault already exists.
4. Use `ai-dememory mcp-config --client codex` to generate Codex MCP config.
5. Use `ai-dememory hooks config --client codex` or
   `ai-dememory hooks config --client claude` to generate optional hook
   fragments. Do not install them without user approval.
6. Use `ai-dememory hooks install --client <client> --dry-run` before writing
   managed `AGENTS.md` or `CLAUDE.md` blocks. Repeated hook captures reuse the
   existing inbox file when provider, event, and payload fingerprint match.
   JSON hook payloads use canonical sorted-key fingerprints.
7. Use `ai-dememory providers detect` and `ai-dememory providers plan --json`
   to inspect possible provider folders and show reviewable configure/import
   commands.
8. Use `ai-dememory capture <kind> --path <file>` or
   `ai-dememory capture text --stdin --title <title>` for explicit one-off
   captures. Confirm the source is non-secret first.
9. Use MCP `memory.git_lessons` or
   `ai-dememory learn --git --days 7 --repo . --dry-run` before writing git
   lesson candidates. Repeat git lesson capture skips candidates with the same
   stable fingerprint.
10. Preview provider configuration after the user chooses a provider and path:
   `ai-dememory providers configure <provider> --path <path> --dry-run --json`.
11. Configure imports only after the user approves the preview:
   `ai-dememory providers configure <provider> --path <path>`.
12. Run `ai-dememory import-chats <provider> --dry-run --json` before writing
   provider import candidates.
13. Show `ai-dememory schedule plan --json` before installing schedules.
   For Docker-based local maintenance, show
   `ai-dememory schedule plan --json --mode docker --image ai-dememory:local`.
   Use `schedule setup --dry-run` only when the user wants shell-ready command
   output after reviewing the structured plan.
14. If the user approves scheduler installation, use
   `ai-dememory schedule setup`.

Package installation is passive. Do not imply that `pip install`,
`pipx install`, plugin installation, or hook config generation starts
background jobs.
