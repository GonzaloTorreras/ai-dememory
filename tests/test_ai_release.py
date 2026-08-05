from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.ai_release_guard import project_version, validate_identity  # noqa: E402
from scripts.published_artifact_guard import compare, local_digests  # noqa: E402
from scripts.eval_recall import summary  # noqa: E402
from scripts.release_artifact_smoke import validate_wheel_namespaces  # noqa: E402


class AiReleaseGuardTests(unittest.TestCase):
    def test_docker_build_context_is_source_allowlisted(self) -> None:
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")

        self.assertNotRegex(dockerfile, r"(?m)^\s*COPY\s+\.\s")
        for source in ("ai_dememory_tool", "scripts", "mcp"):
            self.assertIn(f"COPY {source} ./{source}", dockerfile)
        self.assertTrue(dockerignore.lstrip().startswith("# Deny"))
        self.assertIn("\n**\n", dockerignore)
        for private_root in ("memories", "inbox", "working", "archive"):
            self.assertNotIn(f"!{private_root}/", dockerignore)

    def test_wheel_namespace_guard_rejects_public_package_collisions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            wheel = Path(tmp) / "example.whl"
            with zipfile.ZipFile(wheel, "w") as archive:
                archive.writestr("ai_dememory_tool/__init__.py", "")
                archive.writestr("mcp/__init__.py", "")
                archive.writestr("ai_dememory-2.0.dist-info/METADATA", "")
            with self.assertRaisesRegex(RuntimeError, "unsafe top-level packages"):
                validate_wheel_namespaces(wheel)

    def test_wheel_namespace_guard_rejects_top_level_modules(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            wheel = Path(tmp) / "example.whl"
            with zipfile.ZipFile(wheel, "w") as archive:
                archive.writestr("ai_dememory_tool/__init__.py", "")
                archive.writestr("mcp.py", "")
                archive.writestr("ai_dememory-2.0.dist-info/METADATA", "")
            with self.assertRaisesRegex(RuntimeError, "unsafe top-level packages"):
                validate_wheel_namespaces(wheel)

    def test_wheel_namespace_guard_rejects_data_scheme_packages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            wheel = Path(tmp) / "example.whl"
            with zipfile.ZipFile(wheel, "w") as archive:
                archive.writestr("ai_dememory_tool/__init__.py", "")
                archive.writestr("ai_dememory-2.0.data/purelib/mcp/__init__.py", "")
                archive.writestr("ai_dememory-2.0.dist-info/METADATA", "")
            with self.assertRaisesRegex(RuntimeError, "unsafe top-level packages"):
                validate_wheel_namespaces(wheel)

    def test_wheel_namespace_guard_accepts_private_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            wheel = Path(tmp) / "example.whl"
            with zipfile.ZipFile(wheel, "w") as archive:
                archive.writestr("ai_dememory_tool/__init__.py", "")
                archive.writestr("ai_dememory-2.0.dist-info/METADATA", "")
            self.assertEqual(validate_wheel_namespaces(wheel), {"ai_dememory_tool"})

    def test_empty_recall_has_insufficient_evidence(self) -> None:
        stats = summary([])
        self.assertEqual(stats["status"], "insufficient_evidence")
        self.assertIsNone(stats["recall"])

    def test_current_release_prep_has_exact_dated_identity(self) -> None:
        version = project_version(ROOT)
        identity = validate_identity(ROOT, f"v{version}", version_only=True)

        self.assertEqual(identity.version, version)
        self.assertEqual(identity.tag, f"v{version}")
        self.assertTrue(identity.prerelease)
        self.assertIn(f"## [{version}] - ", identity.changelog_heading)

    def test_dated_version_has_matching_release_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pyproject.toml").write_text(
                '[project]\nname = "ai-dememory"\nversion = "2.1.0"\n',
                encoding="utf-8",
            )
            (root / "CHANGELOG.md").write_text(
                "# Changelog\n\n## [2.1.0] - 2026-07-26\n",
                encoding="utf-8",
            )

            identity = validate_identity(root, "v2.1.0", version_only=True)

        self.assertEqual(identity.version, "2.1.0")
        self.assertEqual(identity.tag, "v2.1.0")
        self.assertEqual(identity.changelog_heading, "## [2.1.0] - 2026-07-26")

    def test_mismatched_and_unversioned_tags_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "does not match project version"):
            validate_identity(ROOT, "v999.0.0", version_only=True)
        with self.assertRaisesRegex(ValueError, "release tag must match"):
            validate_identity(ROOT, "latest", version_only=True)

    def test_published_artifact_recovery_requires_exact_digests(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dist = Path(tmp)
            (dist / "ai_dememory-2.0.0rc2-py3-none-any.whl").write_bytes(b"wheel")
            (dist / "ai_dememory-2.0.0rc2.tar.gz").write_bytes(b"sdist")
            digests = local_digests(dist)
            with patch("scripts.published_artifact_guard.published_digests", return_value=digests):
                self.assertTrue(compare(dist, "testpypi", "2.0.0rc2"))
            with patch("scripts.published_artifact_guard.published_digests", return_value={"wrong.whl": "bad"}):
                with self.assertRaisesRegex(ValueError, "do not match"):
                    compare(dist, "testpypi", "2.0.0rc2")


if __name__ == "__main__":
    unittest.main()
