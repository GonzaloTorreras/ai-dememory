# ADR 0139: MCP Git Lessons

## Status

Accepted

## Context

The v2 roadmap includes git lesson capture so recurring development work can
turn fixes, regressions, CI changes, migrations, deploys, and similar commits
into review-first memory candidates.

The CLI already exposes:

```bash
ai-dememory learn --git --days 7 --repo . --dry-run
```

Codex plugin and MCP users still had to leave the MCP tool surface to preview
or write those candidates. That made git lesson capture less accessible than
provider imports, explicit captures, recall-miss capture, and sleep packets.

## Decision

Expose `memory.git_lessons` on the MCP server.

The tool calls the existing git lesson implementation and accepts:

- `repo` for one local repository path
- `repos` for multiple local repository paths
- `days`
- `limit`
- `dry_run`

`dry_run` defaults to `true`. With the default, the tool inspects local git
history, returns candidate metadata, and writes no files. When `dry_run=false`,
it writes only to `inbox/git-lessons/`; it never promotes durable memory.

The Codex plugin allowlist includes the tool so plugin workflows can preview
git lesson candidates and ask for approval before writing inbox files.

## Consequences

- MCP clients can keep git lesson capture inside the same review-first tool
  surface as imports, recall misses, and sleep packets.
- Plugin setup guidance can use MCP when available and fall back to the CLI
  when needed.
- Runtime smoke verifies the default dry-run boundary with a deterministic
  local git fixture.

## Limitations

- The tool reads local git history from paths supplied by the caller.
- Candidate quality still depends on commit messages and simple keyword
  classification.
- The tool does not deduplicate historical git lesson candidates.
- It does not inspect diffs; it captures commit metadata only.

## Future Work

- Add idempotent git lesson fingerprints if recurring git capture creates
  duplicate inbox candidates.
- Add optional diff summaries after secret-scanning and size limits are
  reviewed.
- Add MCP support for reviewed git lesson promotion if promotion workflows
  become structured.

## Dependencies

- ADR 0008 defines CLI git lesson capture.
- ADR 0068 defines the plugin MCP tool surface guard.
- `scripts/git_lessons.py` remains the shared implementation.

## References

- `scripts/git_lessons.py`
- `mcp/server/memory_mcp.py`
- `plugins/ai-dememory/.mcp.json`
