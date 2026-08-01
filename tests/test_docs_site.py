from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.docs_site_guard import REPO_ROOT, SITE_ROOT, audit_site


class DocumentationSiteGuardTests(unittest.TestCase):
    def test_checked_in_site_passes_guard(self) -> None:
        self.assertEqual([], audit_site())

    def test_guard_rejects_broken_local_link(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            home = copied / "index.html"
            home.write_text(
                home.read_text(encoding="utf-8").replace(
                    'href="architecture/"', 'href="missing/"', 1
                ),
                encoding="utf-8",
            )
            errors = audit_site(REPO_ROOT, copied)
            self.assertTrue(any("broken local reference 'missing/'" in error for error in errors))

    def test_guard_rejects_automatic_external_resource(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            home = copied / "index.html"
            home.write_text(
                home.read_text(encoding="utf-8").replace(
                    "</head>", '<script src="https://example.com/tracker.js"></script></head>', 1
                ),
                encoding="utf-8",
            )
            errors = audit_site(REPO_ROOT, copied)
            self.assertTrue(any("automatic external resource is forbidden" in error for error in errors))

    def test_guard_rejects_external_srcset_resource(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            home = copied / "index.html"
            home.write_text(
                home.read_text(encoding="utf-8").replace(
                    "</main>",
                    '<img src="assets/favicon.svg" srcset="https://example.com/leak.png 2x" alt="">\n</main>',
                    1,
                ),
                encoding="utf-8",
            )
            errors = audit_site(REPO_ROOT, copied)
            self.assertTrue(any("automatic external resource is forbidden" in error for error in errors))

    def test_guard_rejects_inline_css_resource(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            home = copied / "index.html"
            home.write_text(
                home.read_text(encoding="utf-8").replace(
                    "<body>",
                    '<body style="background-image: url(https://example.com/pixel.png)">',
                    1,
                ),
                encoding="utf-8",
            )
            errors = audit_site(REPO_ROOT, copied)
            self.assertTrue(any("inline CSS imports/resources are forbidden" in error for error in errors))

    def test_guard_rejects_source_only_command_in_stable_block(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            home = copied / "index.html"
            home.write_text(
                home.read_text(encoding="utf-8").replace(
                    "ai-dememory setup plan --json",
                    "ai-dememory setup plan --json\nai-dememory setup wizard",
                    1,
                ),
                encoding="utf-8",
            )
            errors = audit_site(REPO_ROOT, copied)
            self.assertTrue(any("stable 2.0.0 command block contains source-only" in error for error in errors))

    def test_guard_rejects_resource_profile_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            install = copied / "install/index.html"
            install.write_text(
                install.read_text(encoding="utf-8").replace("Up to 1,200 tokens", "Up to 1,500 tokens", 1),
                encoding="utf-8",
            )
            errors = audit_site(REPO_ROOT, copied)
            self.assertTrue(any("resource profile 'balanced'" in error for error in errors))

    def test_install_commands_remain_available_without_javascript(self) -> None:
        install = (SITE_ROOT / "install/index.html").read_text(encoding="utf-8")
        self.assertIn("pipx install ai-dememory", install)
        self.assertIn("ai-dememory setup wizard", install)
        self.assertNotIn('class="copy-button"', install)
        self.assertIn("document.createElement(\"button\")", (SITE_ROOT / "assets/site.js").read_text(encoding="utf-8"))

    def test_home_payload_stays_below_documented_budget(self) -> None:
        total = sum(
            path.stat().st_size
            for path in (
                SITE_ROOT / "index.html",
                SITE_ROOT / "assets/site.css",
                SITE_ROOT / "assets/site.js",
            )
        )
        self.assertLessEqual(total, 250 * 1024)


if __name__ == "__main__":
    unittest.main()
