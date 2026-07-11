"""Source-checkout bridge for the packaged ``ai_dememory_tool.admin`` namespace.

Setuptools maps this namespace directly to ``scripts/`` in built artifacts.
This bridge gives source checkouts the same import path without consulting the
current working directory or a configured vault.
"""

from __future__ import annotations

from pathlib import Path
import sys


_SOURCE_ADMIN = Path(__file__).resolve().parents[2] / "scripts"
if _SOURCE_ADMIN.is_dir():
    __path__.append(str(_SOURCE_ADMIN))
    if str(_SOURCE_ADMIN) not in sys.path:
        sys.path.insert(0, str(_SOURCE_ADMIN))
