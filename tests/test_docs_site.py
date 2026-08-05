from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.docs_site_guard import (
    REPO_ROOT,
    SITE_ROOT,
    STABLE_RELEASE_CONTRACTS,
    audit_site,
    release_scope_markers,
    site_release_lens,
)


class DocumentationSiteGuardTests(unittest.TestCase):
    def test_stable_2_1_contract_includes_the_operational_wizard(self) -> None:
        contract = STABLE_RELEASE_CONTRACTS["2.1.0"]

        self.assertIn("ai-dememory setup wizard", contract["required"])
        self.assertIn(
            "pipx install git+https://github.com/GonzaloTorreras/ai-dememory.git",
            contract["source_only"],
        )

    def test_release_scope_supports_source_equal_to_stable(self) -> None:
        self.assertEqual(release_scope_markers("2.1.0", "2.1.0"), ("stable 2.1.0",))
        self.assertEqual(site_release_lens("2.1.0", "2.1.0"), "Source/stable line: 2.1.0")

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

    def test_guard_rejects_external_svg_href_resources(self) -> None:
        for element in ("image", "use"):
            with self.subTest(element=element), tempfile.TemporaryDirectory() as temporary:
                copied = Path(temporary) / "site"
                shutil.copytree(SITE_ROOT, copied)
                home = copied / "index.html"
                home.write_text(
                    home.read_text(encoding="utf-8").replace(
                        "</main>",
                        f'<svg><{element} href="https://github.com/external.svg"></{element}></svg>\n</main>',
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

    def test_guard_rejects_mutable_vcs_install_in_stable_block(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            home = copied / "index.html"
            home.write_text(
                home.read_text(encoding="utf-8").replace(
                    "pipx install ai-dememory",
                    "pipx install git+https://github.com/GonzaloTorreras/ai-dememory.git",
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

    def test_clipboard_fallback_selects_commands_and_updates_accessible_status(self) -> None:
        javascript = (SITE_ROOT / "assets/site.js").read_text(encoding="utf-8")
        self.assertIn("document.createRange()", javascript)
        self.assertIn("range.selectNodeContents(code)", javascript)
        self.assertIn("Clipboard unavailable; commands selected", javascript)
        self.assertIn("Clipboard unavailable; select commands manually", javascript)

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
