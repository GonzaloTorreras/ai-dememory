---
name: memory-maintenance
description: Inspect or run bounded ai-dememory daily and weekly upkeep, provider imports, generated indexes, recall quality, review queues, and scheduler health. Use when the user asks for maintenance, autonomous upkeep, resource consumption, cleanup, or schedule status.
---

# Memory Maintenance

Maintenance is deterministic local Python. It makes zero runtime model or
embedding calls and never promotes durable memory. The default MCP `core`
profile omits maintenance; use the CLI unless the user explicitly selected the
server-enforced `admin` profile.

## Safe Run Order

1. Read state once: `ai-dememory maintenance status`.
2. Preview the selected unit once:
   `ai-dememory maintenance run --profile <daily|weekly> --dry-run --json`.
3. Inspect provider counts, scan/file limits, artifact targets, review queues,
   lock state, and `resource_policy`.
4. Run that profile once only when the preview is acceptable.
5. Read status again and report changed artifacts and remaining review work.

Do not create automatic retry loops. A lock, malformed config, failed provider
read, timeout, or scheduler error requires diagnosis and a fresh preview.

Daily maintenance imports enabled providers into review-only inbox paths,
secret-scans, rebuilds SQLite/graph/lifecycle artifacts, and retains only the
configured number of reports. Provider enumeration, new candidates, file
bytes, hook captures, and report retention are hard-capped by the selected
intensity.

Weekly maintenance adds recall-fixture evaluation, consolidation, hook-capture
review reporting, and a generated sleep plan. It may create review packets but
must not apply them to canonical memory.

## Scheduler

- Inspect: `ai-dememory schedule doctor --json`.
- Plan: `ai-dememory schedule plan --intensity <profile> --json`.
- Apply only the exact `apply_command` returned by the reviewed plan.
- Verify: `ai-dememory schedule status`, then
  `ai-dememory setup health --json`.
- Remove: `ai-dememory schedule remove`.

Tasks are namespaced per vault. A successful install records a receipt but is
not host-verified until status commands succeed. Docker jobs use `--network
none` plus CPU, memory, and PID ceilings. Cron output is export-only and never
installs itself.

## Review Work

Use narrow status commands only when their queue is non-empty:

- Recall: `recall-fixtures status`, then `review-plan`.
- Hook captures: `hooks captures --write-report`.
- False positives/conflicts: `review false-positives --due-only` and
  `review conflicts`.
- Advisory outcomes: `review recommendation-outcomes --json`.
- Release evidence: `release-evidence --json`.

Archive or apply review packets only after explicit approval. Never copy
secrets from provider, hook, malformed, or generated artifacts into reports or
canonical memory.
