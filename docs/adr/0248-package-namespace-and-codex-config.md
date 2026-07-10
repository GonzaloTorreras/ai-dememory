# ADR 0248: Private package namespaces and native Codex configuration

## Status

Accepted on 2026-07-10.

## Context

The release-candidate wheel accidentally exposed the generic top-level Python
packages `mcp` and `scripts`. Installing it could shadow the official MCP SDK
and make import behavior depend on installation order. The project also claimed
Python 3.10 support while importing `tomllib`, and generated a JSON
`mcpServers` object for Codex even though Codex reads MCP servers from TOML.

An empty recall fixture set was additionally reported as perfect recall, which
allowed readiness summaries to confuse absence of evidence with success.

## Decision

Publish only the `ai_dememory_tool` top-level package. Map the existing MCP and
administrative source trees into the private installed namespaces
`ai_dememory_tool.mcp_server` and `ai_dememory_tool.admin`. The exact built wheel
is rejected if it exposes any other import-package namespace.

Require Python 3.11 or newer. Generate native `[mcp_servers.ai-dememory]` TOML
for Codex while retaining JSON output for clients that use JSON. Represent an
empty recall evaluation as `insufficient_evidence` with a null recall value.

## Safety invariants

- installing ai-dememory never creates or replaces a top-level `mcp` package;
- the release smoke validates the built wheel, not only packaging metadata;
- the official MCP SDK and ai-dememory must import together in an isolated
  environment;
- Codex output must parse as TOML before release;
- zero evaluated retrievals can never satisfy a recall threshold.

## Consequences

Python 3.10 is no longer supported. Internal installed-module paths differ from
their source-checkout paths, so the CLI resolves both layouts explicitly. A
cross-platform Python 3.11-3.13 CI matrix guards the supported package contract.

## Dependencies

- setuptools explicit package mapping;
- Python standard-library `tomllib` and `zipfile`;
- the official MCP Python package used by the compatibility job;
- Codex MCP configuration semantics documented by OpenAI.

## Limitations

The source checkout retains its historical `mcp/` and `scripts/` directories.
They are safe in the wheel but can still shadow environment packages when a
developer runs Python with the repository root first on `sys.path`.

The large MCP tool surface and coarse setup-health summary are not reduced by
this packaging correction; they require a separately versioned compatibility
design.

## Future Risks

Adding a new package without updating the explicit setuptools map could omit it
from distributions. Conversely, weakening the artifact guard could reintroduce
namespace collisions. Client configuration formats may evolve, so generated
Codex TOML must remain covered by parser and launch smokes.
