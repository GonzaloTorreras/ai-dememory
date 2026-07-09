# ADR 0238: MCP Publish Plan Smoke

## Status

Accepted

## Context

ADR 0237 exposed read-only MCP tool `memory.publish_plan`. Source runtime smoke
proved the tool worked from the repository checkout, but distribution users run
the installed package or the local Docker image. A release could therefore pass
source MCP checks while still missing packaged proof that the MCP publish plan
is callable from a fresh private vault.

The publish plan is intentionally non-publishing, so smoke coverage must verify
side-effect flags and manual dispatch inputs without contacting GitHub, PyPI,
or TestPyPI.

## Decision

Add installed-package and Docker smoke coverage for MCP `memory.publish_plan`.

Package install smoke runs:

```bash
ai-dememory mcp --call memory.publish_plan --args "{}"
```

Docker smoke runs the equivalent local image command with the vault mounted at
`/memory` and `AI_DEMEMORY_ROOT=/memory`:

```bash
docker run --rm -v <vault>:/memory -e AI_DEMEMORY_ROOT=/memory ai-dememory:local mcp --call memory.publish_plan --args "{}"
```

Both paths reuse the publish-plan validator already used by CLI smoke. The
validator requires TestPyPI as the default repository, manual dispatch and
confirmation inputs, non-empty preflight commands and next actions,
`runs_commands=true` for local read-only inspection, and false values for
`mutates_system`, `runs_publish_commands`, `runs_preflight_commands`,
`writes_files`, and `publishes_package`.

## Consequences

- CI proves `memory.publish_plan` works from source, installed wheel, and local
  Docker image paths.
- Release checklists and guards now name the package and Docker smoke commands.
- Distribution smoke remains local-only and does not publish packages or mutate
  host scheduler or repository state.

## Limitations

- Smoke coverage does not verify GitHub environment protection rules, Trusted
  Publisher configuration, or live PyPI/TestPyPI state.
- Docker smoke still depends on Docker availability in CI or the local host.
- The fresh-vault smoke exercises unavailable release evidence inside the plan,
  not a completed release-ready distribution checkout.

## Future Work

- Add post-TestPyPI verification smoke only after a real TestPyPI publish
  defines reviewed acceptance evidence.
- Add optional workflow URL resolution only if a GitHub connector-backed
  release dashboard needs live metadata.
- Keep remote build systems out of scope until remote distribution is approved.

## Dependencies

- ADR 0127 defines publish workflow package and Docker smoke gates.
- ADR 0236 defines the CLI publish plan.
- ADR 0237 defines MCP publish planning.
- `scripts/install_smoke.py` owns installed package and Docker smoke.
- `scripts/publish_plan.py` owns publish plan validation semantics.
- `.github/workflows/ci.yml` runs install smoke and Docker local MCP smoke.

## References

- `scripts/install_smoke.py`
- `scripts/publish_plan.py`
- `tests/test_memory_tools.py`
- `docs/release-v2-checklist.md`
