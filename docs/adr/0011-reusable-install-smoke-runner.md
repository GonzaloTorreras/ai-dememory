# ADR 0011: Reusable Install Smoke Runner

## Status

Accepted for v2 draft.

## Context

The v2 release requires confidence that `ai-dememory` can be installed as a
Python package, initialized into a separate private vault, run as a local MCP
server, and run through the local Docker MCP image. CI had this coverage as
inline shell, but users and maintainers also need a repeatable local command
before TestPyPI or PyPI publishing.

## Decision

Add `ai-dememory install-smoke`, backed by `scripts/install_smoke.py`.

By default the command creates a fresh virtual environment, installs the package
specifier, creates a temporary private vault, and verifies:

- vault init
- doctor, validate, secret scan, index, recall fixtures, and vector gate
- MCP config generation for installed and Docker modes
- provider detection, hook config, hook install dry-run, schedule dry-run, and
  maintenance status
- explicit Markdown capture and git lesson dry-run
- MCP `initialize` and `ping` through the installed CLI

With `--skip-package --docker`, the command builds the local Docker image,
bind-mounts a temporary vault at `/memory`, runs doctor/index, and verifies MCP
`initialize` and `ping` over stdio.

GitHub Actions now calls this command for package and Docker smoke instead of
duplicating the shell flow.

## Benefits

- Gives maintainers the same install gate locally and in CI.
- Exercises a broader installed CLI surface than the previous inline smoke.
- Keeps package install and Docker smoke behavior in versioned Python code.
- Reduces CI drift when install requirements change.

## Limitations

- The package smoke is intentionally slower than unit tests because it creates a
  fresh virtual environment and installs the package.
- Docker smoke still depends on a local Docker runtime.
- The command validates local stdio behavior only; it does not prove a real GUI
  MCP client can launch the server.

## Future Risks

- Future package dependencies may make the smoke too slow for every PR.
- Docker mount behavior can differ across Windows, WSL, macOS, and Linux.
- If package data layout changes, installed CLI commands that depend on checkout
  docs must remain clearly separated from vault commands.
