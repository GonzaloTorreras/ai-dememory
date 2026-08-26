from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from maintenance import (  # noqa: E402
    REVIEW_STATE_ERROR_MESSAGE,
    dry_run_maintenance,
    main as maintenance_main,
    maintenance_status,
)
from mcp.server.memory_mcp import call_tool  # noqa: E402
from provider_import import (  # noqa: E402
    ProviderImportError,
    REDACTED_PROVIDER_FILE,
    configure_provider,
    import_chats,
    main as provider_main,
    provider_setup_plan,
    providers_status,
    read_provider_file,
)
from review_memory import ReviewError  # noqa: E402


PATH_CANARY = "cfg-diag-003-private-provider-path"
READ_CANARY = "cfg-diag-003-private-read-failure"


class ProviderDiagnosticRedactionTests(unittest.TestCase):
    @staticmethod
    def _render(value: object) -> str:
        return json.dumps(value, sort_keys=True, default=str)

    @staticmethod
    def _assert_no_generated_state(root: Path) -> None:
        for relative in ("inbox", "indexes", "reports"):
            if (root / relative).exists():
                raise AssertionError(f"unexpected generated state: {relative}")

    def assert_exception_chain_redacted(self, error: BaseException, *canaries: str) -> None:
        seen: set[int] = set()
        current: BaseException | None = error
        while current is not None and id(current) not in seen:
            seen.add(id(current))
            rendered = f"{type(current).__name__}: {current!s} {current!r}"
            for canary in canaries:
                self.assertNotIn(canary, rendered)
            current = current.__cause__ or current.__context__

    def test_missing_path_failures_are_redacted_without_changing_status_shapes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = parent / "vault"
            missing = parent / PATH_CANARY / "missing"
            root.mkdir()
            configure_provider(root, "codex", missing)
            config_before = (root / ".ai-dememory.toml").read_bytes()

            with self.assertRaises(ProviderImportError) as direct_error:
                import_chats(root, "codex", dry_run=True)

            provider_stdout = io.StringIO()
            provider_stderr = io.StringIO()
            with redirect_stdout(provider_stdout), redirect_stderr(provider_stderr):
                provider_exit = provider_main(
                    ["--root", str(root), "import", "codex", "--dry-run", "--json"]
                )

            # MCP loads the packaged mirror of this module, so its safe error
            # class has a distinct identity while retaining the same contract.
            with self.assertRaises(ValueError) as mcp_error:
                call_tool(
                    "memory.import_chats",
                    {"provider": "codex", "dry_run": True},
                    root,
                )

            preview = dry_run_maintenance(root, "daily")
            maintenance_stdout = io.StringIO()
            maintenance_stderr = io.StringIO()
            with redirect_stdout(maintenance_stdout), redirect_stderr(maintenance_stderr):
                maintenance_exit = maintenance_main(
                    ["--root", str(root), "run", "--dry-run", "--json"]
                )

            status = providers_status(root)
            plan = provider_setup_plan(root)
            maintenance = maintenance_status(root)
            status_item = next(item for item in status["providers"] if item["name"] == "codex")
            plan_item = next(item for item in plan["providers"] if item["name"] == "codex")

            error_surfaces = "\n".join(
                (
                    str(direct_error.exception),
                    provider_stdout.getvalue(),
                    provider_stderr.getvalue(),
                    str(mcp_error.exception),
                    self._render(preview["would_imports"]),
                    maintenance_stdout.getvalue(),
                    maintenance_stderr.getvalue(),
                )
            )

            self.assertEqual(direct_error.exception.code, "provider_path_missing")
            self.assertIsNone(direct_error.exception.__cause__)
            self.assertIsNone(direct_error.exception.__context__)
            self.assertEqual(provider_exit, 1)
            self.assertEqual(provider_stdout.getvalue(), "")
            self.assertEqual(maintenance_exit, 0)
            self.assertEqual(maintenance_stderr.getvalue(), "")
            self.assertIn("provider_path_missing", error_surfaces)
            self.assertNotIn(PATH_CANARY, error_surfaces)
            self.assertNotIn(str(missing), error_surfaces)
            self.assertNotIn("Traceback", error_surfaces)
            self.assert_exception_chain_redacted(mcp_error.exception, PATH_CANARY, str(missing))

            # Read-only administrative projections deliberately retain their
            # pre-existing paths and schemas for review and compatibility.
            self.assertEqual(status_item["path"], str(missing.resolve()))
            self.assertEqual(
                set(status_item),
                {"name", "path", "exists", "configured", "enabled", "import_ready", "reason"},
            )
            self.assertEqual(plan_item["path"], str(missing.resolve()))
            self.assertIn(str(missing.resolve()), plan_item["configure_command"])
            self.assertEqual(maintenance["providers"]["codex"]["path"], str(missing.resolve()))
            self.assertEqual((root / ".ai-dememory.toml").read_bytes(), config_before)
            self._assert_no_generated_state(root)

    def test_unsafe_path_and_unexpected_failures_use_closed_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = parent / "vault"
            source = parent / PATH_CANARY / "provider"
            root.mkdir()
            source.mkdir(parents=True)
            configure_provider(root, "codex", source)

            with patch("provider_import.path_is_link_like", return_value=True):
                with self.assertRaises(ProviderImportError) as direct_error:
                    import_chats(root, "codex", dry_run=True)
                stderr = io.StringIO()
                with redirect_stderr(stderr):
                    exit_code = provider_main(
                        ["--root", str(root), "import", "codex", "--dry-run", "--json"]
                    )
                preview = dry_run_maintenance(root, "daily")

            internal = OSError(f"{READ_CANARY}: {source}")
            unexpected_stderr = io.StringIO()
            with (
                patch("provider_import.import_chats", side_effect=internal),
                redirect_stderr(unexpected_stderr),
            ):
                unexpected_exit = provider_main(
                    ["--root", str(root), "import", "codex", "--dry-run", "--json"]
                )
            with patch("maintenance.import_chats", side_effect=internal):
                unexpected_preview = dry_run_maintenance(root, "daily")

            rendered = "\n".join(
                (
                    str(direct_error.exception),
                    stderr.getvalue(),
                    self._render(preview),
                    unexpected_stderr.getvalue(),
                    self._render(unexpected_preview),
                )
            )
            self.assertEqual(direct_error.exception.code, "provider_path_unsafe")
            self.assertEqual(exit_code, 1)
            self.assertEqual(unexpected_exit, 1)
            self.assertIn("provider_path_unsafe", rendered)
            self.assertIn("provider_import_failed", rendered)
            self.assertNotIn(PATH_CANARY, rendered)
            self.assertNotIn(READ_CANARY, rendered)
            self.assertNotIn("Traceback", rendered)
            self._assert_no_generated_state(root)

    def test_read_error_record_and_helper_exception_are_path_free(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = parent / "vault"
            source = parent / "provider"
            root.mkdir()
            source.mkdir()
            source_file = source / f"{PATH_CANARY}.jsonl"
            source_file.write_text('{"message":"Reviewed fixture."}\n', encoding="utf-8")
            configure_provider(root, "codex", source)
            failure = OSError(f"{READ_CANARY}: {source_file}")

            with patch("provider_import._read_provider_file", side_effect=failure):
                with self.assertRaises(ProviderImportError) as helper_error:
                    read_provider_file(source_file, source, 1024)

            with patch("provider_import.read_provider_file", side_effect=failure):
                direct = import_chats(root, "codex", dry_run=True)
                provider_stdout = io.StringIO()
                provider_stderr = io.StringIO()
                with redirect_stdout(provider_stdout), redirect_stderr(provider_stderr):
                    provider_exit = provider_main(
                        ["--root", str(root), "import", "codex", "--dry-run", "--json"]
                    )
                maintenance_preview = dry_run_maintenance(root, "daily")

            provider_payload = json.loads(provider_stdout.getvalue())
            for result in (direct, provider_payload, maintenance_preview["would_imports"][0]):
                self.assertEqual(
                    result["skipped"],
                    [
                        {
                            "path": REDACTED_PROVIDER_FILE,
                            "reason": "provider source could not be read [provider_read_failed] (provider=codex)",
                        }
                    ],
                )
                self.assertEqual(result["source_path"], str(source.resolve()))
                self.assertNotIn(PATH_CANARY, self._render(result["skipped"]))
                self.assertNotIn(READ_CANARY, self._render(result["skipped"]))

            self.assertEqual(helper_error.exception.code, "provider_read_failed")
            self.assertIsNone(helper_error.exception.__cause__)
            self.assertIsNone(helper_error.exception.__context__)
            self.assert_exception_chain_redacted(
                helper_error.exception,
                PATH_CANARY,
                READ_CANARY,
                str(source_file),
            )
            self.assertEqual(provider_exit, 0)
            self.assertEqual(provider_stderr.getvalue(), "")
            self._assert_no_generated_state(root)

    def test_unknown_provider_identifier_is_not_reflected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(ProviderImportError) as raised:
                import_chats(root, PATH_CANARY, dry_run=True)

        self.assertEqual(raised.exception.code, "unknown_provider")
        self.assertIsNone(raised.exception.provider)
        self.assertNotIn(PATH_CANARY, str(raised.exception))

    def test_maintenance_review_error_boundary_discards_message_and_cause(self) -> None:
        def chained_review_error(_root: Path, *_args: object) -> object:
            try:
                raise OSError(f"{READ_CANARY}: {PATH_CANARY}")
            except OSError as cause:
                raise ReviewError(f"review failed at {PATH_CANARY}") from cause

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "vault"
            root.mkdir()
            (root / ".ai-dememory.toml").write_text(
                '[memory]\nschema_version = "2.0"\n',
                encoding="utf-8",
            )
            before = list(root.iterdir())

            with patch("maintenance._maintenance_status", side_effect=chained_review_error):
                with self.assertRaises(ReviewError) as direct_error:
                    maintenance_status(root)
                stdout = io.StringIO()
                stderr = io.StringIO()
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    exit_code = maintenance_main(["--root", str(root), "status", "--json"])

            self.assertEqual(str(direct_error.exception), REVIEW_STATE_ERROR_MESSAGE)
            self.assertIsNone(direct_error.exception.__cause__)
            self.assertIsNone(direct_error.exception.__context__)
            self.assertEqual(exit_code, 2)
            self.assertEqual(stdout.getvalue(), "")
            self.assertEqual(stderr.getvalue().strip(), REVIEW_STATE_ERROR_MESSAGE)
            self.assertNotIn(PATH_CANARY, stderr.getvalue())
            self.assertNotIn(READ_CANARY, stderr.getvalue())
            self.assertNotIn("Traceback", stderr.getvalue())
            self.assertEqual(list(root.iterdir()), before)


if __name__ == "__main__":
    unittest.main()
