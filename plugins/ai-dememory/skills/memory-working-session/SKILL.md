---
name: memory-working-session
description: Maintain generated ai-dememory working state and handoffs through MCP or CLI tools. Use when the user asks to remember current task state, prepare a handoff, resume recent work, summarize a session, or update local working memory without promoting durable facts.
---

# Memory Working Session

Use working-memory tools for operational session state only. Working files are
not canonical durable memory and must not be treated as reviewed facts.

Preferred MCP workflow:

1. Call `memory.working_status` before resuming work to see whether current
   task state, recent-session notes, or handoffs exist.
2. Call `memory.working_current` when the status shows current task state that
   may affect the answer.
3. Call `memory.context` when the user needs broader recall; it already includes
   working state unless disabled by the caller.
4. Call `memory.working_snapshot` after a meaningful task step or before a long
   interruption. Include a short title, optional task name, and concise notes.
5. Call `memory.working_handoff` when the user asks to hand off, pause, or leave
   continuation instructions.
6. Use `memory.write_proposal` or explicit CLI capture only for facts that may
   become durable memory, keeping them in review-first inbox paths.

CLI fallback:

- `ai-dememory working current`
- `ai-dememory working status --json`
- `ai-dememory working snapshot --title <title> --task <task> --notes <notes>`
- `ai-dememory working handoff --title <title> --notes <notes>`

Safety rules:

- Never place secrets, tokens, cookies, private keys, service account JSON, or
  `.env` content in working notes.
- Treat `working/current.json`, `working/recent-session.md`, and
  `working/handoffs/` as generated operational state.
- Do not promote working state to durable memory without explicit human review.
- Keep handoffs concise enough for the next agent to verify from repository and
  PR state instead of trusting the handoff blindly.
