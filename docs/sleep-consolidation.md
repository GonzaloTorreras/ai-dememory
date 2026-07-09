# Sleep Consolidation

Sleep consolidation turns maintenance findings into a review queue. It is safe
by default: it does not edit, archive, supersede, or promote canonical memory.

Generate a plan:

```bash
ai-dememory sleep --dry-run
ai-dememory sleep --dry-run --json
ai-dememory sleep plan
ai-dememory sleep plan --report-path reports/sleep-plan.md
ai-dememory sleep plan --json
ai-dememory sleep plan --json --json-report-path reports/sleep-plan.json
```

`sleep --dry-run` previews the same candidates without writing reports or
packets. Custom report paths must stay inside the memory root. Rendered
Markdown and JSON sleep plans are secret-scanned before writing.

Write review packets:

```bash
ai-dememory sleep --propose
ai-dememory sleep --propose --id sleep_... --json
ai-dememory sleep --apply-reviewed --id sleep_... --json
ai-dememory sleep --apply-reviewed --all
ai-dememory sleep apply-reviewed --id sleep_...
ai-dememory sleep apply-reviewed --all
```

Review packets are written under `inbox/sleep-consolidation/`. They summarize
why a candidate needs attention and what safe action a human should consider.
The `--propose` alias writes review packets only; it does not edit canonical
memory and is equivalent to proposing sleep review work into the inbox.
The `--apply-reviewed` alias is a roadmap-compatible wrapper around
`sleep apply-reviewed`; it requires `--id` or `--all` and writes the same
review packets without applying canonical changes.

Candidate sources:

- inbox captures awaiting review
- active memory conflicts
- due or low-confidence memories
- lifecycle `needs_repair` and `review_due` recommendations
- unreviewed secret-scan findings, with redacted evidence only

MCP clients can call `memory.sleep_plan` to inspect candidates. The
`memory.sleep_apply_reviewed` tool writes review packets only; it does not
modify canonical memories.

Run validation before promoting anything from the sleep inbox:

```bash
ai-dememory validate
ai-dememory secret-scan
```
