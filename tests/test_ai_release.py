from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.ai_release_guard import changelog_heading, project_version, validate_identity
from scripts.published_artifact_guard import compare, local_digests


ROOT = Path(__file__).resolve().parents[1]


class AiReleaseGuardTests(unittest.TestCase):
    def test_current_version_has_matching_release_identity(self) -> None:
        version = project_version(ROOT)
        identity = validate_identity(ROOT, f"v{version}", version_only=True)

        self.assertEqual(identity.version, version)
        self.assertEqual(identity.tag, f"v{version}")
        self.assertEqual(identity.changelog_heading, changelog_heading(ROOT, version))

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
