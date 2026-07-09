# ADR 0224: Maintenance Artifact Freshness

Status: Accepted

## Context

Scheduled daily and weekly maintenance rebuilds disposable indexes, graph data,
weights, lifecycle scores, lifecycle reports, and review reports. Existing
maintenance status exposed whether those generated artifacts existed and when
they were last written, but it did not directly say whether a maintenance run
was needed after canonical Markdown changed.

Users evaluating cron jobs, Docker-backed maintenance, or release handoffs need
a read-only answer to "are generated artifacts missing or stale?" without
running maintenance or mutating the vault.

## Decision

Add a compact `artifact_freshness` object to:

- `ai-dememory maintenance status --json`;
- `ai-dememory maintenance run --profile <daily|weekly> --dry-run --json`;
- `ai-dememory maintenance run` results and generated maintenance reports;
- MCP `memory.maintenance_status` and dry-run `memory.maintenance_run`;
- `ai-dememory setup health --json` and MCP `memory.setup_health`; and
- release evidence setup and maintenance summaries.

The freshness summary compares known generated artifact timestamps with the
latest canonical memory Markdown timestamp. It reports source count, latest
source path/time, missing count, stale count, fresh count, per-artifact status,
and a `needs_maintenance` flag.

This is read-only. It does not run maintenance, rebuild indexes, refresh
weights, write lifecycle reports, delete packet archives, install schedules, or
mutate canonical memory.

## Benefits

- Scheduler setup can explain when recurring maintenance would refresh stale
  or missing generated artifacts.
- MCP clients can decide whether to recommend a daily maintenance dry-run
  without parsing timestamps themselves.
- Release evidence now shows generated artifact freshness alongside setup and
  maintenance summaries.
- Package and Docker install smokes verify the status contract.

## Limitations

- Freshness is based on filesystem modification times, not content hashes.
- It compares artifacts against canonical memory Markdown, not every possible
  input such as provider chat files or runtime retrieval logs.
- A missing weekly-only hook capture report can still make the summary report
  maintenance as needed after a daily run.

## Future Risks

- If generated artifacts gain source manifests, freshness should move from
  mtime comparison to manifest/hash comparison.
- If provider imports become part of freshness, the summary must avoid reading
  provider chat files unless a user explicitly runs an import or dry-run.
- If cleanup becomes configurable, freshness should stay separate from retention
  decisions so stale artifacts are not deleted automatically.

## Dependencies

- ADR 0055 defines generated artifact status in maintenance.
- ADR 0153 defines setup health summaries.
- ADR 0185 defines setup health in release evidence.
- ADR 0222 defines maintenance summaries in release evidence.
- `scripts/maintenance.py` owns maintenance status and reports.
- `scripts/setup_plan.py` owns setup health.
- `scripts/release_evidence.py` owns release evidence summaries.
