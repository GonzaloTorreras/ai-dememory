"""Source-contract checks, not a replacement for a real GitHub/OIDC run."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1] / ".github" / "workflows"


class ReleaseWorkflowTests(unittest.TestCase):
    def test_tagger_dispatches_same_tuple_with_scoped_permissions(self):
        text = (ROOT / "tag-release.yml").read_text(encoding="utf-8")
        tag, dispatch = text.split("\n  publish:\n")
        self.assertIn("test \"$(git cat-file -t", tag)
        self.assertIn("needs: tag", dispatch)
        self.assertIn("actions: write", dispatch)
        self.assertNotIn("actions: write", tag)
        self.assertNotIn("checkout", dispatch.split("    steps:")[1].lower())
        self.assertIn('gh workflow run release.yml --repo "$GITHUB_REPOSITORY" --ref main', dispatch)
        self.assertIn('-f tag="$RELEASE_TAG" -f approved_sha="$APPROVED_SHA"', dispatch)
        self.assertIn('confirm="publish-$RELEASE_TAG@$APPROVED_SHA"', dispatch)

    def test_all_versions_use_pypi_but_keep_prerelease_label(self):
        text = (ROOT / "release.yml").read_text(encoding="utf-8")
        self.assertNotIn("publish-testpypi", text)
        self.assertNotIn("test.pypi.org", text)
        self.assertNotIn("if: needs.validate.outputs.prerelease", text)
        self.assertIn("INDEX=https://pypi.org/simple/", text)
        self.assertIn('extra+=(--prerelease)', text)
        self.assertIn("needs: [validate, build, publish-pypi]", text)

    def test_standalone_publisher_retains_identity_and_oidc_checks(self):
        text = (ROOT / "release.yml").read_text(encoding="utf-8")
        self.assertNotIn("workflow_call", text)
        self.assertIn('test "$RELEASE_CONFIRM" = "publish-$RELEASE_TAG@$APPROVED_SHA"', text)
        self.assertIn('test "$(git cat-file -t', text)
        self.assertIn("workflows/ci.yml/runs", text)
        self.assertIn("name: pypi", text)
        self.assertIn("id-token: write", text)
        self.assertIn("python -m twine check dist/*", text)
        self.assertNotIn("skip-existing", text)


if __name__ == "__main__":
    unittest.main()
