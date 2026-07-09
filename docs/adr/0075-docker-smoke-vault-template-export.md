# ADR 0075: Docker Smoke Vault Template Export

Status: Accepted for the v2 draft.

## Context

ADR 0073 added `ai-dememory vault-template export <path>` for creating a
separate private GitHub vault template repository. ADR 0074 added installed
package smoke coverage so the console script path proves packaged template data
is present.

Docker is the reproducible local MCP path. The image installs the same package,
but Docker smoke only proved vault initialization, doctor, index, maintenance
status, release-evidence boundaries, MCP lifecycle, and generated Docker client
config behavior. It did not prove that the image can export the packaged vault
template.

## Decision

Extend Docker smoke to run:

```bash
docker run --rm -v <temp-template-repo>:/template \
  ai-dememory:local vault-template export /template --force --json
```

The smoke validates the JSON response and representative exported files with
the same validator used by installed package smoke. It requires hidden config
files, the top-level README, durable-memory README, and LLM capture inbox README
to exist in the mounted template directory.

## Benefits

- Proves the local Docker image contains the packaged vault template export
  path.
- Keeps Docker distribution behavior aligned with the installed CLI setup path.
- Catches image packaging drift before users rely on Docker for MCP or setup
  flows.

## Limitations

- The check requires Docker and only runs where Docker is available.
- It validates representative files rather than a full tree checksum.
- It does not create or configure a GitHub template repository.
- The host creates the empty mount directory first; the container writes into
  that bind mount with `--force`.

## Future Risks

- If multiple templates are added, Docker smoke should cover the default and
  at least one explicit selector.
- Docker mount behavior differs across platforms; Windows and WSL path handling
  may require a future normalization helper.
- If the template export command grows GitHub API integration, Docker smoke
  should keep repository creation disabled by default.

## Dependencies

- ADR 0053 defines Docker smoke release-evidence coverage.
- ADR 0057 defines Docker maintenance artifact status coverage.
- ADR 0073 defines the vault template export command.
- ADR 0074 defines installed package smoke coverage for the same command.
- `scripts/install_smoke.py` remains the shared package and Docker smoke
  runner.
