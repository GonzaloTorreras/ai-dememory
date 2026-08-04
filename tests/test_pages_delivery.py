from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from ci_guard import (  # noqa: E402
    PAGES_DEPLOY_WORKFLOW_PATH,
    PAGES_VALIDATE_WORKFLOW_PATH,
    validate_pages_deploy_workflow_text,
    validate_pages_validation_workflow_text,
)
from pages_artifact_guard import (  # noqa: E402
    audit_artifact_tree,
    audit_pages_artifact,
    git_blob_object_id,
    parse_index_flags,
    parse_git_manifest,
)


class PagesWorkflowGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.validation = (ROOT / PAGES_VALIDATE_WORKFLOW_PATH).read_text(encoding="utf-8")
        self.deployment = (ROOT / PAGES_DEPLOY_WORKFLOW_PATH).read_text(encoding="utf-8")

    def test_current_pages_workflows_pass_boundary_guards(self) -> None:
        self.assertEqual([], validate_pages_validation_workflow_text(self.validation))
        self.assertEqual([], validate_pages_deploy_workflow_text(self.deployment))

    def test_validation_workflow_rejects_write_or_deploy_capabilities(self) -> None:
        weakened = (
            self.validation
            + "\n  workflow_dispatch:\n"
            + "\npermissions:\n  pages: write\n  id-token: write\n"
            + "\njobs:\n  deploy:\n    environment: github-pages\n"
            + "    steps:\n      - uses: actions/deploy-pages@deadbeef\n"
        )

        issues = validate_pages_validation_workflow_text(weakened)
        targets = {issue.target for issue in issues}

        self.assertIn("pages-validate.yml:workflow_dispatch", targets)
        self.assertIn("pages-validate.yml:pages_write", targets)
        self.assertIn("pages-validate.yml:oidc", targets)
        self.assertIn("pages-validate.yml:environment", targets)
        self.assertIn("pages-validate.yml:deploy", targets)

    def test_deploy_workflow_rejects_automatic_trigger_and_broad_permissions(self) -> None:
        weakened = (
            self.deployment.replace("  workflow_dispatch:\n", "  workflow_dispatch:\n  push:\n")
            .replace("pages: write", "contents: write\n      pages: write")
            .replace("permissions: {}", "permissions:\n  actions: write")
        )

        issues = validate_pages_deploy_workflow_text(weakened)
        targets = {issue.target for issue in issues}

        self.assertIn("pages.yml:push", targets)
        self.assertIn("pages.yml:contents_write", targets)
        self.assertIn("pages.yml:actions_write", targets)

    def test_deploy_workflow_requires_live_main_tuple_and_exact_site_path(self) -> None:
        weakened = (
            self.deployment.replace(
                'gh api "repos/$GITHUB_REPOSITORY/commits/main" --jq .sha',
                "printf stale-main",
            )
            .replace('test "$live_main_sha" = "$APPROVED_SHA"', "true")
            .replace("path: site", "path: .")
        )

        issues = validate_pages_deploy_workflow_text(weakened)
        targets = {issue.target for issue in issues}

        self.assertIn("pages.yml:live_main_query", targets)
        self.assertIn("pages.yml:live_main_match", targets)
        self.assertIn("pages.yml:artifact_path", targets)

    def test_deploy_job_rejects_shell_or_extra_actions(self) -> None:
        weakened = self.deployment + "\n      - name: Unsafe shell\n        run: echo unsafe\n"

        issues = validate_pages_deploy_workflow_text(weakened)

        self.assertIn("pages.yml:deploy_steps", {issue.target for issue in issues})

    def test_deploy_workflow_requires_guard_immediately_before_upload(self) -> None:
        weakened = self.deployment.replace(
            "      - name: Upload exact GitHub Pages artifact",
            "      - name: Mutate artifact after guard\n"
            "        run: touch site/untracked.txt\n\n"
            "      - name: Upload exact GitHub Pages artifact",
        )

        issues = validate_pages_deploy_workflow_text(weakened)

        self.assertIn("pages.yml:guard_upload_adjacency", {issue.target for issue in issues})

    def test_deploy_workflow_revalidates_after_environment_gate(self) -> None:
        weakened = self.deployment.replace(
            "      - name: Revalidate current main after environment gate",
            "      - name: Trust stale preparation result",
            1,
        )

        issues = validate_pages_deploy_workflow_text(weakened)

        self.assertIn("pages.yml:deploy_revalidation", {issue.target for issue in issues})


class PagesArtifactGuardTests(unittest.TestCase):
    def test_checked_in_site_matches_tracked_manifest(self) -> None:
        self.assertEqual([], audit_pages_artifact(ROOT, require_clean=False))

    def test_manifest_rejects_symlink_gitlink_and_unmerged_entries(self) -> None:
        object_id = b"a" * 40
        raw = (
            b"120000 " + object_id + b" 0\tsite/link\0"
            b"160000 " + object_id + b" 0\tsite/submodule\0"
            b"100644 " + object_id + b" 2\tsite/conflict.html\0"
        )

        _, errors = parse_git_manifest(raw)
        combined = "\n".join(errors)

        self.assertIn("found 120000", combined)
        self.assertIn("found 160000", combined)
        self.assertIn("unmerged at stage 2", combined)

    def test_index_flags_reject_assume_unchanged_and_skip_worktree(self) -> None:
        errors = parse_index_flags(
            b"h site/index.html\0S site/install/index.html\0",
            {"index.html", "install/index.html"},
        )
        combined = "\n".join(errors)

        self.assertIn("index flag 'h' is forbidden", combined)
        self.assertIn("index flag 'S' is forbidden", combined)

    def test_tree_rejects_untracked_files_and_unexpected_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            site = Path(temporary) / "site"
            site.mkdir()
            (site / "index.html").write_text("ok", encoding="utf-8")
            (site / "extra.txt").write_text("unexpected", encoding="utf-8")
            (site / "empty").mkdir()

            errors = audit_artifact_tree(site, {"index.html": git_blob_object_id(site / "index.html")})
            combined = "\n".join(errors)

            self.assertIn("site/extra.txt: artifact file is not tracked by Git", combined)
            self.assertIn("site/empty: artifact directory is not implied by tracked files", combined)

    def test_tree_rejects_hard_links(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            site = Path(temporary) / "site"
            site.mkdir()
            first = site / "index.html"
            second = site / "copy.html"
            first.write_text("same inode", encoding="utf-8")
            try:
                os.link(first, second)
            except OSError as exc:
                self.skipTest(f"hard links are unavailable: {exc}")

            object_id = git_blob_object_id(first)
            errors = audit_artifact_tree(site, {"index.html": object_id, "copy.html": object_id})

            self.assertTrue(any("hard-linked files are forbidden" in error for error in errors))

    def test_tree_rejects_content_that_does_not_match_tracked_blob(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            site = Path(temporary) / "site"
            site.mkdir()
            page = site / "index.html"
            page.write_text("approved", encoding="utf-8")
            approved_object_id = git_blob_object_id(page)
            page.write_text("mutated", encoding="utf-8")

            errors = audit_artifact_tree(site, {"index.html": approved_object_id})

            self.assertTrue(any("content does not canonicalize to tracked Git blob" in error for error in errors))

    def test_guard_rejects_assume_unchanged_content_bypass(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            site = root / "site"
            site.mkdir()
            page = site / "index.html"
            page.write_text("approved", encoding="utf-8")

            def git(*arguments: str) -> None:
                subprocess.run(
                    ["git", *arguments],
                    cwd=root,
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )

            git("init", "--quiet")
            git("add", "site/index.html")
            git(
                "-c",
                "user.name=Pages Guard Test",
                "-c",
                "user.email=pages-guard@example.invalid",
                "commit",
                "--quiet",
                "-m",
                "fixture",
            )
            git("update-index", "--assume-unchanged", "site/index.html")
            page.write_text("hidden mutation", encoding="utf-8")

            errors = audit_pages_artifact(root)
            combined = "\n".join(errors)

            self.assertIn("index flag 'h' is forbidden", combined)
            self.assertIn("content does not canonicalize to tracked Git blob", combined)


if __name__ == "__main__":
    unittest.main()
