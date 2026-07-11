"""Source-checkout bridge for the packaged MCP server namespace.

The wheel maps this namespace directly to ``mcp/server``.  The source bridge
uses only the repository location derived from this file and never loads code
from a vault or the current working directory.
"""

from __future__ import annotations

from pathlib import Path


_SOURCE_MCP_SERVER = Path(__file__).resolve().parents[2] / "mcp" / "server"
if _SOURCE_MCP_SERVER.is_dir():
    __path__.append(str(_SOURCE_MCP_SERVER))
