from __future__ import annotations

import io
from contextlib import redirect_stdout
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from ai_dememory_tool.cli import mcp_config  # noqa: E402
from hook_event import main as hook_main  # noqa: E402
from http_api import main as api_main  # noqa: E402
from maintenance import main as maintenance_main  # noqa: E402
from onboarding import main as onboarding_main  # noqa: E402
from provider_import import main as provider_main  # noqa: E402
from schedule_memory import main as schedule_main  # noqa: E402
from setup_plan import main as setup_main  # noqa: E402


class RuntimeBindingHelpTests(unittest.TestCase):
    def test_runtime_help_explains_explicit_saved_default_without_cwd_lookup(self) -> None:
        entrypoints = (
            ("mcp config", mcp_config, ["--help"]),
            ("API", api_main, ["--help"]),
            ("maintenance", maintenance_main, ["--help"]),
            ("onboarding", lambda args: onboarding_main(args, mode="operational"), ["--help"]),
            ("provider", provider_main, ["plan", "--help"]),
            ("setup", setup_main, ["--help"]),
            ("schedule", schedule_main, ["--help"]),
            ("hook capture", hook_main, ["capture", "--help"]),
            ("hook dispatch", hook_main, ["dispatch", "--help"]),
            ("hook list", hook_main, ["list", "--help"]),
            ("hook config", hook_main, ["config", "--help"]),
        )

        for label, entrypoint, argv in entrypoints:
            with self.subTest(entrypoint=label):
                output = io.StringIO()
                with redirect_stdout(output), self.assertRaises(SystemExit) as raised:
                    entrypoint(argv)

                self.assertEqual(raised.exception.code, 0)
                help_text = " ".join(output.getvalue().split())
                self.assertIn(
                    "Resolution order: --root, AI_DEMEMORY_ROOT, then a saved local default",
                    help_text,
                )
                self.assertIn(
                    "ai-dememory vault use <absolute-vault-path>",
                    help_text,
                )
                self.assertIn(
                    "uses the working directory to discover a vault",
                    help_text,
                )
