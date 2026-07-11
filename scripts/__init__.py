"""Runtime modules for the ai-dememory command line tool.

The project still supports executing individual modules directly from a source
checkout, where their historical imports are top-level module names.  Expose
the package directory for those internal imports when this directory is mapped
to :mod:`ai_dememory_tool.admin` in an installed distribution.  Public package
consumers can then import the namespaced modules without relying on CLI setup.
"""

from __future__ import annotations

from pathlib import Path
import sys


_ADMIN_MODULE_DIR = Path(__file__).resolve().parent
if str(_ADMIN_MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(_ADMIN_MODULE_DIR))
