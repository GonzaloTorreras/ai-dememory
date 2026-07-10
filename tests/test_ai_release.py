from __future__ import annotations

from pathlib import Path
import unittest

from scripts.ai_release_guard import changelog_heading, project_version, validate_identity


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


if __name__ == "__main__":
    unittest.main()
