# ADR 0234: Roadmap Status Smoke Coverage

## Status

Accepted

## Context

ADR 0232 added `ai-dememory roadmap status` and ADR 0233 exposed the same
status through MCP. Those paths prove the distribution checkout and MCP runtime
can inspect the v2 roadmap, but they do not prove the packaged CLI or local
Docker image can run the same check after installation.

The roadmap status command is useful as a continuation handoff only if it works
through the install paths users are expected to run: a wheel-installed
`ai-dememory` command and the local stdio Docker image.

## Decision

Add roadmap status to package install smoke and Docker smoke.

Package install smoke runs `ai-dememory roadmap status --json` from a fresh
vault after installing the package into a temporary virtual environment. Docker
smoke runs `ai-dememory roadmap status --json` inside the local image with the
test vault bind-mounted at `/memory` and `AI_DEMEMORY_ROOT=/memory`.

Both smoke paths validate that the payload is JSON, reports 11 roadmap phases,
has matching status counts, includes stable phase numbers, and leaves
`writes_files=false` and `mutates_files=false`.

The smoke runner accepts exit code `1` only for the roadmap status command,
because a plain vault can correctly report missing distribution evidence while
still returning a valid read-only status payload.

## Consequences

- Release checks cover roadmap status across source, installed package, MCP,
  and Docker surfaces.
- Docker smoke continues to exercise only local stdio/container behavior and
  does not expose an HTTP service.
- Plain vaults can still report missing implementation evidence because the
  implementation evidence lives in the distribution checkout.
- A missing-evidence roadmap status remains visible in smoke results as exit
  code `1`, but it does not fail install or Docker smoke by itself.
- The release checklist guard catches removal of the installed and Docker
  roadmap status smoke requirements.

## Limitations

- Smoke validation checks payload shape and read-only behavior; it does not run
  every phase's underlying behavioral tests.
- Fresh vault smoke does not require all phases to be implemented because a
  vault mount is not a full distribution checkout.
- Docker smoke depends on local Docker availability in environments that choose
  to run `install-smoke --docker`.

## Future Work

- Add per-phase smoke tags if roadmap phases become directly mapped to test
  commands.
- Include package-version metadata in roadmap status if release handoffs need
  to compare installed package and source checkout versions.
- Add a Docker-specific MCP `memory.roadmap_status` smoke if a future client
  needs that exact transport path.

## Dependencies

- ADR 0011 defines the reusable install smoke runner.
- ADR 0018 expands install smoke across v2 CLI surfaces.
- ADR 0026 defines Docker maintenance schedule planning.
- ADR 0232 defines CLI roadmap status.
- ADR 0233 defines MCP roadmap status.
- `scripts/install_smoke.py` owns installed package and Docker smoke commands.

## References

- `scripts/install_smoke.py`
- `scripts/roadmap_status.py`
- `docs/release-v2-checklist.md`
- `scripts/release_checklist_guard.py`
- `tests/test_memory_tools.py`
