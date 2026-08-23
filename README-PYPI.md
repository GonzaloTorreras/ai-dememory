# ai DeMemory

ai DeMemory is a local-first memory toolchain for people who work with more
than one AI assistant. It provides a Python CLI, an optional local MCP server,
review-first memory workflows, and a private vault whose Markdown files remain
the canonical data.

## Install

Use Python 3.11 or newer. For a published stable release on the default PyPI
index:

```bash
python -m pip install --upgrade ai-dememory
```

Prereleases and non-default indexes require the exact version and index command
on the matching [GitHub Release](https://github.com/GonzaloTorreras/ai-dememory/releases).
Do not assume the default PyPI command installs a prerelease.

## Start

Use the wizard-first command documented by that matching release; older
releases can retain a compatibility flag. The wizard creates bounded local
operating policy. It does not start a daemon, schedule background work, call a
model, or promote durable memories. Follow-up actions such as MCP
configuration, a loopback-only local API, indexing, hooks, and schedules are
optional and explicit.

## Trust boundary

Keep the private vault outside source checkouts and do not place credentials,
tokens, private keys, or personal memories in this public package repository.
SQLite indexes and generated reports are disposable; approved Markdown remains
the portable source of truth.

For full documentation, exact release artifacts, compatibility notes, and
prerelease availability, see the
[ai DeMemory repository](https://github.com/GonzaloTorreras/ai-dememory).
