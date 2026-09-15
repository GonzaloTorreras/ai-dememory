# Setup, hooks and scheduled work

Install the V3 package, then run `ai-dememory setup`. The interactive setup
explains each optional integration; answering no keeps a passive local vault.
No provider account is required to save or recall memory.

For the complete optional Windows + Codex setup without prompts:

```powershell
ai-dememory setup --with-codex --with-schedule --yes
ai-dememory serve workbench
```

An existing selected vault is reused. No V2 import or conversation scan happens.
Setup enables the relevant modules but does not log into providers or start a
dashboard/server automatically. If an optional integration fails, the vault
remains ready; the error identifies the incomplete step. Re-running is safe for
unchanged owned configuration. Unrelated settings and credentials are preserved.

## What each hook does

| Codex event | Useful behavior | Extra model calls |
| --- | --- | --- |
| UserPromptSubmit | Retrieves relevant project/global memory for a nontrivial prompt | None |
| SessionStart | Explains scoped recall and evidenced learning at startup, resume, clear and after compact | None |

The host assistant uses its existing model and native MCP tools to learn an
explicit durable statement or verified outcome. Inference stays provisional;
correction and undo remain available. A hook does not guarantee the assistant
will learn on every turn. It does not read full transcripts or store raw prompts.

Restart Codex, open `/hooks`, and trust both generated definitions. Installation
does not bypass native trust or tool approval. The existing prompt command stays
unchanged when adding SessionStart. Project-local integrations retain their
existing prompt hook; the session hook belongs to the global Codex installer.

No Stop hook forces another turn: Codex's blocking Stop result continues model
execution and could create unwanted loops. No per-tool watcher is installed.
These choices follow the [official Codex hook contract](https://learn.chatgpt.com/docs/hooks).

## Scheduled consolidation without a dashboard process

The optional Windows task checks the **same single saved schedule** every hour.
A new schedule defaults to global, weekly (168 hours). Existing scope/cadence
are preserved. Use Consolidation in the dashboard to change them, pause the job,
inspect last result/error, or run now. Advanced setup overrides are
`--schedule-scope project:NAME --schedule-hours 24` with `--with-schedule`.

- Runs as the logged-in installing user, with least privilege and no password.
- Does not wake the PC or run while logged out. A due run waits for an available
  check; it does not replay every missed interval.
- No new resident process, watcher, listener or Node dependency. Each check exits.
- Windows task limit: five minutes; overlapping task launches are ignored.
  A shared vault lock also prevents a dashboard tick consuming the same deadline.
- At most 100 active memories in the exact scope are inspected. Exact duplicate
  cleanup is local and reversible. No provider means no model calls.
- Only global consolidation can use its configured provider/fallback to propose
  a shorter summary for review. Project cleanup makes zero model calls.
- Existing daily call/token/cost budgets apply. Budget prices are estimates, not
  invoice controls. Third-party provider plugins remain trusted Python code.
- A browser-session API key is unavailable outside its workbench process. Use
  an environment credential available to the scheduled user, a configured local
  provider or the separately enabled/authenticated Codex subscription adapter.
  The installer never copies credentials into the task.
- Source-folder/history schedules **still require the foreground workbench**.
  Installing this task does not authorize or enable conversation extraction.

The task name and owned XML are recorded privately in `windows-task.json` in
the vault. Keep this operational receipt with backups; it is not a memory or a
search index. The UI reads that receipt, not live Windows health. For live status:

```powershell
ai-dememory serve workbench --task status
```

The Windows settings use official [interactive-token registration](https://learn.microsoft.com/en-us/windows/win32/taskschd/taskfolder-registertask)
and [IgnoreNew overlap handling](https://learn.microsoft.com/en-us/windows/win32/taskschd/taskschedulerschema-multipleinstancespolicy-settingstype-element).

## Disable or remove

Pause Consolidation in the dashboard to stop future jobs. Disable `workbench`
to make subsequent one-shot checks skip all consolidation. Remove its OS task
before disabling the module if you also want to remove hourly launches:

```powershell
ai-dememory serve workbench --task remove
ai-dememory serve harness-codex uninstall --user
```

Removal checks exact ownership and refuses to overwrite later user edits.
No memories, provider accounts or unrelated tasks/settings are deleted. Restart
Codex to unload removed hooks/MCP connections. A task already running is not
silently terminated by uninstall; pause/remove at an idle boundary.

On other systems, use the existing foreground dashboard or call
`ai-dememory serve workbench --run-due` from your own scheduler. It checks once
and exits, without starting HTTP or running source ingestion. This release does
not install cron, launchd, services or remote networking.
