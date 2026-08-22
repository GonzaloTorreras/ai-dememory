# Documentation Portal

ai DeMemory has two deliberately separate locations:

- the **public tool repository**, which contains source code, package
  documentation, and public demo/validation fixtures; and
- a **separately bound private vault**, which contains the Markdown memory you
  actually use.

Choose the guide for the task in front of you. Installation does not require
reading source-checkout or release procedures.

## Install And Start A Vault

- [Install](install.md): the stable 2.1.0 path, the TestPyPI 2.1.1rc1
  evaluation path, the wizard, and bounded intensity choices.
- [Create a memory repository](create-memory-repo.md): create a reusable
  private GitHub vault template when one local vault is not enough.
- [Operations](operations.md): diagnose, upgrade, maintain, and recover an
  existing private vault.

## Use It Locally

- [Local MCP](local-mcp.md): connect Codex, Claude, or another client through
  local stdio, with a bound vault, server-enforced profile, and idle lease.
- [MCP client configuration](mcp-client-config.md): inspectable configuration
  for Codex, Claude, and generic clients.
- [Local REST API](local-api.md): optional loopback HTTP for a local script or
  dashboard. The current unreleased source line may suggest it after the
  wizard; start it manually with `ai-dememory --root ~/code/my-memory api`.
  It runs in the foreground and is not started automatically.
- [Hooks](hooks.md) and [scheduler](scheduler.md): optional, trust-gated local
  integrations and maintenance automation.

## Work With Memory Safely

- [Safety and security policy](../SECURITY.md): secret handling and reporting.
- [Schema](schema.md), [memory quality](memory-quality.md), and
  [review workflows](review-workflows.md): canonical Markdown, review, and
  retrieval-quality rules.
- [Import and capture](import-capture.md),
  [source-grounded queries](source-grounded-query-design.md), and
  [consolidation](sleep-consolidation.md): bring material into a review-first
  vault without turning raw conversation data into durable memory.

## Understand The Product

- [Architecture](architecture.md): local-first components and generated state.
- [Memory graph](memory-graph.md): the bounded graph and its local API.
- [MCP V2](mcp-v2.md) and its [gap analysis](mcp-v2-gap-analysis.md): protocol
  surface and compatibility boundaries.
- [Public modernization roadmap](public-modernization-roadmap.md): product
  direction. It is explanatory, not an executable implementation queue.

## Contribute Or Prepare A Release

These guides apply to a reviewed source checkout, not ordinary local use:

- [Development continuity](../DEVELOPMENT.md) and
  [development status](development-status.md): current public branch,
  frontier, and evidence boundary.
- [Distribution](distribution.md): package and release procedures.
- [V3 execution roadmap](v3-hybrid-visual-multiplatform-roadmap.md) and
  [machine-readable planning contracts](../contracts/planning/): normative
  future task order and state.
- [ADRs](adr/): source-level decisions and historical context.

For the concise product entry point, return to the [root README](../README.md).
