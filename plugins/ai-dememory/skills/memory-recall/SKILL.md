---
name: memory-recall
description: Recall relevant local ai-dememory facts through MCP tools. Use when the user asks to remember, recall, search memory, inspect memory graph relationships, or ground a task in previous decisions.
---

# Memory Recall

Use MCP tools before searching the filesystem directly.

Steps:

1. Call `memory.context` when the user needs session-start context or a compact
   bundle within a token budget. Use an explicit `query` for targeted recall;
   use `auto: true` when generated working memory is the best session-start
   query source.
2. Call `memory.working_status` when current task state or a previous handoff
   would materially change the answer, then call `memory.working_current` only
   if current state exists.
3. Call `memory.search` with a focused query for targeted recall.
4. Call `memory.get` only for relevant public/internal results.
5. Use `memory.graph` when relationship context matters, such as related tags,
   project decisions, or references between memories.
6. Cite memory IDs in your answer when a memory influenced the result.
7. Use `memory.outcome` to record good/bad usefulness only when the user asks or
   when a workflow explicitly calls for feedback capture.

Do not request sensitive memory unless the user explicitly asks. Never treat
inbox/import candidates or generated working state as durable fact until
reviewed.
