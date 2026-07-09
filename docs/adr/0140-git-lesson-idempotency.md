# ADR 0140: Git Lesson Idempotency

## Status

Accepted

## Context

Git lesson capture turns recent fix, regression, CI, build, migration, auth,
deploy, and related commits into review-first inbox candidates. The CLI and MCP
tool both write candidates under `inbox/git-lessons/`.

After ADR 0139 exposed git lesson capture to MCP, the workflow became easier to
run from agents and recurring maintenance-style routines. The existing writer
used timestamped filenames, so rerunning capture against the same repository
and commit could create duplicate review candidates.

## Decision

Compute a stable git lesson fingerprint from repository path, short commit SHA,
and commit subject before rendering the candidate.

Include the fingerprint in the candidate filename and rendered `source`
metadata. Before previewing or writing a candidate, check `inbox/git-lessons/`
for an existing candidate with the same slug and fingerprint. If one exists,
skip the candidate with reason `already captured` and return the existing inbox
path.

Dry-run follows the same duplicate check and does not report duplicate writes.

## Consequences

- Repeated CLI and MCP git lesson capture does not create duplicate inbox files
  for the same commit lesson.
- Reviewers can trace duplicate skips to the existing candidate path.
- The behavior matches provider import idempotency while keeping git lesson
  state Markdown-canonical.

## Limitations

- The fingerprint includes the repository path, so moving a repository can
  create a new candidate for the same commit.
- The fingerprint uses the commit subject, not the full commit body or diff.
- Existing candidates created before this filename convention may not be
  detected as duplicates.

## Future Work

- Add optional content-only deduplication if repository moves produce too much
  duplicate review work.
- Add a bounded manifest only if filename scanning becomes too slow.
- Consider diff-aware fingerprints if git lesson capture starts summarizing
  changed files.

## Dependencies

- ADR 0008 defines CLI git lesson capture.
- ADR 0139 defines MCP git lesson capture.
- ADR 0138 defines the equivalent provider import idempotency pattern.

## References

- `scripts/git_lessons.py`
- `mcp/server/memory_mcp.py`
- `tests/test_memory_tools.py`
