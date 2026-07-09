# ADR 0197: Review Recommendation Archive Status

Status: Accepted

## Context

ADR 0196 added CLI-only archival for accepted/rejected advisory recommendation
artifacts. That moved reviewed recommendation artifacts out of
`inbox/review-recommendations/`, keeping active queues focused on pending work.

After archival, reviewers still needed structured access to historical
accepted/rejected recommendation outcomes without inspecting Markdown files by
hand or relying on Git history alone.

## Decision

Add read-only CLI command `ai-dememory review recommendations-archive-status`.

The command reads archived recommendation artifacts under
`archive/review-recommendations/` and returns:

- total and returned counts;
- accepted and rejected counts;
- kind counts;
- malformed archived artifact counts;
- filtered recommendation records;
- side-effect flags showing it does not write files, apply decisions, or mutate
  canonical memory.

The command supports `--kind`, `--outcome-status accepted|rejected`,
`--archive-root`, `--limit`, and `--json`. Custom archive roots must stay under
`archive/review-recommendations/`.

## Benefits

- Reviewers can inspect archived recommendation outcomes as audit history.
- Active recommendation queue status remains focused on pending work.
- Release and install smoke can verify archive command wiring without moving
  files.
- The same parser validates active and archived recommendation frontmatter.

## Limitations

- The status command is read-only; ADR 0198 defines the separate restore
  command for reopening one archived artifact.
- ADR 0201 adds optional recursive scanning for partitioned archives.
- ADR 0202 adds offset pagination for large archive history.
- ADR 0200 exposes the same archive status read model over MCP.

## Future Work

- Add stable cursor tokens only if offset pagination proves insufficient.

## Dependencies

- ADR 0188 defines advisory recommendation artifacts.
- ADR 0191 defines accepted/rejected recommendation outcomes.
- ADR 0196 defines CLI-only archival for accepted/rejected recommendation
  artifacts.
- `scripts/review_memory.py` owns recommendation artifact parsing and archive
  status.
- ADR 0200 defines MCP archive status.
- ADR 0201 defines optional recursive archive partition scans.
- ADR 0202 defines archive status pagination.
- `scripts/install_smoke.py` verifies installed CLI command wiring.
