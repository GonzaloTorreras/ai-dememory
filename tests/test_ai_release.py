from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import ctypes
import io
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import tomllib
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.ai_release_guard import (  # noqa: E402
    changelog_release_notes,
    main as release_guard_main,
    project_version,
    validate_identity,
    write_release_notes,
)
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
        self.assertIn(
            'CMD ["mcp", "--stdio", "--idle-timeout-seconds", "600", '
            '"--profile", "core", '
            '"--require-bound-root"]',
            dockerfile,
        )

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
        self.assertEqual(identity.prerelease, bool(re.search(r"(?:a|b|rc)[0-9]+$", version)))
        self.assertIn(f"## [{version}] - ", identity.changelog_heading)

    def test_packaged_readme_is_release_state_neutral(self) -> None:
        metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        readme = ROOT / str(metadata["project"]["readme"])
        text = readme.read_text(encoding="utf-8")
        lowered = text.lower()

        self.assertEqual(readme.name, "README-PYPI.md")
        self.assertIn("# ai DeMemory", text)
        self.assertIn("ai-dememory init /path/to/my-memory --wizard", text)
        for stale_claim in ("untagged", "unpublished", "source candidate"):
            self.assertNotIn(stale_claim, lowered)

    def test_dated_version_has_matching_release_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pyproject.toml").write_text(
                '[project]\nname = "ai-dememory"\nversion = "2.1.0"\n',
                encoding="utf-8",
            )
            (root / "CHANGELOG.md").write_text(
                "# Changelog\n\n## [2.1.0] - 2026-07-26\n\n- Ship the release.\n",
                encoding="utf-8",
            )

            identity = validate_identity(root, "v2.1.0", version_only=True)

        self.assertEqual(identity.version, "2.1.0")
        self.assertEqual(identity.tag, "v2.1.0")
        self.assertEqual(identity.changelog_heading, "## [2.1.0] - 2026-07-26")

    def test_release_notes_are_the_exact_version_section_with_comparison_link(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "CHANGELOG.md").write_text(
                """# Changelog

## [2.2.0] - Unreleased

- Future work must stay out of these notes.

## [2.1.0] - 2026-07-26

- Ship the complete historical release.

[Compare v2.0.0...v2.1.0](https://github.com/GonzaloTorreras/ai-dememory/compare/v2.0.0...v2.1.0)

## [2.0.0] - 2026-07-10

- Previous release must stay out of these notes.
""",
                encoding="utf-8",
            )

            notes = changelog_release_notes(root, "2.1.0")

        self.assertEqual(
            notes,
            """## [2.1.0] - 2026-07-26

- Ship the complete historical release.

[Compare v2.0.0...v2.1.0](https://github.com/GonzaloTorreras/ai-dememory/compare/v2.0.0...v2.1.0)
""",
        )
        self.assertNotIn("Future work", notes)
        self.assertNotIn("Previous release", notes)

    def test_release_notes_reject_indented_h2_boundaries(self) -> None:
        for spaces in (1, 2, 3):
            with self.subTest(spaces=spaces), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "CHANGELOG.md").write_text(
                    """# Changelog

## [2.1.0] - 2026-07-26

Current release only.

{indent}## [2.0.0] - 2026-07-10

- Previous release must stay out.
""".format(indent=" " * spaces),
                    encoding="utf-8",
                )

                with self.assertRaisesRegex(ValueError, "indented ATX H2"):
                    changelog_release_notes(root, "2.1.0")

    def test_release_notes_reject_fences_and_html_comments(self) -> None:
        fixtures = {
            "fence": "```markdown\n## [9.9.9] - 2099-01-01\n```",
            "comment": "<!--\n## [8.8.8] - 2088-01-01\n-->",
        }
        for label, construct in fixtures.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "CHANGELOG.md").write_text(
                    f"# Changelog\n\n## [2.1.0] - 2026-07-26\n\n{construct}\n",
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(ValueError, "unsupported"):
                    changelog_release_notes(root, "2.1.0")

    def test_release_notes_reject_unclosed_markdown_structures(self) -> None:
        fixtures = {
            "fence": """# Changelog

## [2.1.0] - 2026-07-26

- Before.

```markdown
## Not a real section
""",
            "comment": """# Changelog

## [2.1.0] - 2026-07-26

- Before.

<!--
## Not a real section
""",
        }
        for label, changelog in fixtures.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "CHANGELOG.md").write_text(changelog, encoding="utf-8")

                with self.assertRaisesRegex(ValueError, "unsupported"):
                    changelog_release_notes(root, "2.1.0")

    def test_release_notes_reject_comment_markers_even_when_inline_or_indented(self) -> None:
        fixtures = {
            "inline": "- literal `<!--`",
            "multi-backtick-inline": "- literal ``code <!-- marker``",
            "indented": "    <!-- literal code",
        }
        for label, literal in fixtures.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "CHANGELOG.md").write_text(
                    f"""# Changelog

## [2.1.0] - 2026-07-26

{literal}

## [2.0.0] - 2026-07-10

- Previous release must stay out.

- literal `-->`
""",
                    encoding="utf-8",
                )

                with self.assertRaisesRegex(ValueError, "HTML comments are unsupported"):
                    changelog_release_notes(root, "2.1.0")

    def test_release_notes_reject_raw_html_blocks_that_can_hide_headings(self) -> None:
        fixtures = {
            "fake-target": """# Changelog

<pre>
## [2.1.0] - 2026-07-26
- Fake target.
</pre>

## [2.0.0] - 2026-07-10
- Previous release.
""",
            "fake-boundary": """# Changelog

## [2.1.0] - 2026-07-26
- Real target.

<div>
## [9.9.9] - 2099-01-01
</div>

- Must not be truncated.
""",
        }
        for label, changelog in fixtures.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "CHANGELOG.md").write_text(changelog, encoding="utf-8")

                with self.assertRaisesRegex(ValueError, "raw HTML blocks are unsupported"):
                    changelog_release_notes(root, "2.1.0")

    def test_release_notes_preserve_first_indented_code_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "CHANGELOG.md").write_text(
                """# Changelog

## [2.1.0] - 2026-07-26

    print("must stay code")

## [2.0.0] - 2026-07-10
- Previous release.
""",
                encoding="utf-8",
            )

            notes = changelog_release_notes(root, "2.1.0")

        self.assertIn('\n\n    print("must stay code")\n', notes)

    def test_release_notes_reject_sections_containing_only_chained_comments(self) -> None:
        fixtures = (
            "<!-- first --><!-- second -->",
            "<!-- first --> <!-- second -->",
        )
        for comments in fixtures:
            with self.subTest(comments=comments), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "pyproject.toml").write_text(
                    '[project]\nname = "ai-dememory"\nversion = "2.1.0"\n',
                    encoding="utf-8",
                )
                (root / "CHANGELOG.md").write_text(
                    f"""# Changelog

## [2.1.0] - 2026-07-26

{comments}

## [2.0.0] - 2026-07-10
- Previous release.
""",
                    encoding="utf-8",
                )

                with self.assertRaisesRegex(ValueError, "HTML comments are unsupported"):
                    validate_identity(root, "v2.1.0", version_only=True)

    def test_release_notes_reject_a_comment_reopened_on_the_same_line(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "CHANGELOG.md").write_text(
                """# Changelog

## [2.1.0] - 2026-07-26
- Real content.

<!-- first --> <!--
## [9.9.9] - 2099-01-01
-->

- Content after the hidden heading.

## [2.0.0] - 2026-07-10
- Previous release.
""",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "HTML comments are unsupported"):
                changelog_release_notes(root, "2.1.0")

    def test_release_notes_reject_quote_heavy_custom_raw_html_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "CHANGELOG.md").write_text(
                """# Changelog

<x data-note=">">
## [2.1.0] - 2026-07-26
- Fake target.

## [2.0.0] - 2026-07-10
- Previous release.
""",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "raw HTML blocks are unsupported"):
                changelog_release_notes(root, "2.1.0")

    def test_release_notes_allow_standard_markdown_autolinks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "CHANGELOG.md").write_text(
                """# Changelog

## [2.1.0] - 2026-07-26

<https://example.com/releases/2.1.0> release details

## [2.0.0] - 2026-07-10
- Previous release.
""",
                encoding="utf-8",
            )

            notes = changelog_release_notes(root, "2.1.0")

        self.assertIn("<https://example.com/releases/2.1.0> release details", notes)

    def test_release_notes_reject_nested_list_h2_as_ambiguous(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "CHANGELOG.md").write_text(
                """# Changelog

## [2.1.0] - 2026-07-26

- Feature example:
  ## Nested example heading
  - Nested detail.

- Must remain in 2.1.0.

## [2.0.0] - 2026-07-10
- Previous release.
""",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "indented ATX H2"):
                changelog_release_notes(root, "2.1.0")

    def test_release_notes_reject_nested_h2_after_lazy_list_continuation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "CHANGELOG.md").write_text(
                """# Changelog

## [2.1.0] - 2026-07-26

- Feature example
lazy continuation of the feature paragraph
  ## Nested example heading
  - Nested detail.

- Must remain in 2.1.0.

## [2.0.0] - 2026-07-10
- Previous release.
""",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "indented ATX H2"):
                changelog_release_notes(root, "2.1.0")

    def test_release_notes_reject_ambiguous_list_block_interrupts(self) -> None:
        interrupts = {
            "fence": "```text\nexample\n```",
            "block-quote": "> quoted release context",
            "html-comment": "<!-- reviewed release boundary -->",
        }
        for label, interrupt in interrupts.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "CHANGELOG.md").write_text(
                    f"""# Changelog

## [2.1.0] - 2026-07-26

1. Current release item
{interrupt}
   ## [2.0.0] - 2026-07-10

- Previous release must stay out.

## [1.0.0] - 2026-06-01

- Older release.
""",
                    encoding="utf-8",
                )

                with self.assertRaisesRegex(
                    ValueError,
                    "fenced code blocks|HTML comments|indented ATX H2",
                ):
                    changelog_release_notes(root, "2.1.0")

    def test_release_notes_reject_fence_markers_in_lazy_list_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "CHANGELOG.md").write_text(
                """# Changelog

## [2.1.0] - 2026-07-26

1. Current release item
```invalid`info
   ## Nested example heading
   Nested content must remain in this release.

## [2.0.0] - 2026-07-10

- Previous release.
""",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "fenced code blocks"):
                changelog_release_notes(root, "2.1.0")

    def test_release_notes_reject_indented_h2_after_loose_list_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "CHANGELOG.md").write_text(
                """# Changelog

## [2.1.0] - 2026-07-26

- Current release item


  ## Nested example after a loose list block

- Nested content must remain in the current release.

## [1.0.0] - 2026-06-01

- Older release.
""",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "indented ATX H2"):
                changelog_release_notes(root, "2.1.0")

    def test_release_notes_fail_closed_on_commonmark_list_ambiguities(self) -> None:
        payloads = {
            "ordered-noninterrupt": (
                "Paragraph continues\n"
                "2. not actually a list interrupt\n"
                "   ## [2.0.0] - 2026-01-01\n"
                "- Adjacent content"
            ),
            "empty-list-item": (
                "Paragraph continues\n"
                "+ \n"
                "  ## [2.0.0] - 2026-01-01\n"
                "- Adjacent content"
            ),
            "stale-list-state": (
                "- ## Nested heading\n"
                "outdented paragraph\n"
                "  ## [2.0.0] - 2026-01-01\n"
                "- Adjacent content"
            ),
            "list-fence": (
                "- ```\n"
                "  target code\n"
                "  ```\n"
                "## [2.0.0] - 2026-01-01\n"
                "- Adjacent content"
            ),
        }
        for label, payload in payloads.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "CHANGELOG.md").write_text(
                    "# Changelog\n\n## [2.1.0] - 2026-07-26\n\n"
                    + payload
                    + "\n\n## [1.0.0] - 2025-01-01\n- Older content.\n",
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(
                    ValueError,
                    "indented ATX H2|fenced code blocks",
                ):
                    changelog_release_notes(root, "2.1.0")

    def test_release_notes_reject_non_commonmark_line_separators(self) -> None:
        for separator in (
            "\x0b",
            "\x0c",
            "\x1c",
            "\x1d",
            "\x1e",
            "\x85",
            "\u2028",
            "\u2029",
        ):
            with self.subTest(separator=repr(separator)), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "CHANGELOG.md").write_text(
                    "# Changelog\n\n## [2.1.0] - 2026-07-26\n\n"
                    f"- Current content{separator}## [2.0.0] - 2026-01-01\n"
                    "- Adjacent content\n",
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(ValueError, "non-CommonMark line separator"):
                    changelog_release_notes(root, "2.1.0")

    def test_release_notes_reject_setext_h2_or_ambiguous_dash_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "CHANGELOG.md").write_text(
                """# Changelog

## [2.1.0] - 2026-07-26

- Current release.

[2.0.0] - 2026-07-10
--------------------

- Previous release.
""",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "Setext H2"):
                changelog_release_notes(root, "2.1.0")

    def test_release_notes_reject_later_top_level_h1_boundaries(self) -> None:
        boundaries = {
            "atx": "# Separate top-level section",
            "setext": "Separate top-level section\n==========================",
        }
        for label, boundary in boundaries.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "CHANGELOG.md").write_text(
                    "# Changelog\n\n## [2.1.0] - 2026-07-26\n\n"
                    "- Current release.\n\n"
                    f"{boundary}\n\n"
                    "Content outside the target release section.\n",
                    encoding="utf-8",
                )

                with self.assertRaisesRegex(ValueError, "H1 boundaries are unsupported"):
                    changelog_release_notes(root, "2.1.0")

    def test_release_identity_rejects_an_empty_exact_section(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pyproject.toml").write_text(
                '[project]\nname = "ai-dememory"\nversion = "2.1.0"\n',
                encoding="utf-8",
            )
            (root / "CHANGELOG.md").write_text(
                """# Changelog

## [2.1.0] - 2026-07-26

<!-- A hidden placeholder is not publishable release content. -->

## [2.0.0] - 2026-07-10

- Content from another version must not be reused.
""",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "HTML comments are unsupported"):
                validate_identity(root, "v2.1.0", version_only=True)

    def test_release_identity_rejects_duplicate_version_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pyproject.toml").write_text(
                '[project]\nname = "ai-dememory"\nversion = "2.1.0"\n',
                encoding="utf-8",
            )
            (root / "CHANGELOG.md").write_text(
                """# Changelog

## [2.1.0] - Unreleased

- Stale draft.

## [2.1.0] - 2026-07-26

- Dated release.
""",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, r"multiple \[2\.1\.0\] release headings"):
                validate_identity(root, "v2.1.0", version_only=True)

    def test_release_notes_cli_writes_reproducible_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "RELEASE_NOTES.md"
            (root / "pyproject.toml").write_text(
                '[project]\nname = "ai-dememory"\nversion = "2.1.0"\n',
                encoding="utf-8",
            )
            (root / "CHANGELOG.md").write_text(
                "# Changelog\r\n\r\n## [2.1.0] - 2026-07-26\r\n\r\n- Deterministic notes.\r\n",
                encoding="utf-8",
                newline="",
            )
            argv = [
                "--root",
                str(root),
                "--tag",
                "v2.1.0",
                "--version-only",
                "--release-notes",
                str(output),
            ]

            with redirect_stdout(io.StringIO()):
                self.assertEqual(release_guard_main(argv), 0)
            first = output.read_bytes()
            output.unlink()
            with redirect_stdout(io.StringIO()):
                self.assertEqual(release_guard_main(argv), 0)
            second = output.read_bytes()

        self.assertEqual(first, b"## [2.1.0] - 2026-07-26\n\n- Deterministic notes.\n")
        self.assertEqual(second, first)

    def test_release_notes_output_is_exclusive_and_repository_contained(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            (root / "CHANGELOG.md").write_text(
                """# Changelog

## [2.1.0] - 2026-07-26

- Deterministic notes.
""",
                encoding="utf-8",
            )
            existing = root / "existing.md"
            existing.write_text("preserve", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "already exists"):
                write_release_notes(root, "2.1.0", existing)
            with self.assertRaisesRegex(ValueError, "inside the repository root"):
                write_release_notes(root, "2.1.0", root.parent / "outside.md")
            outside_parent = root.parent / "must-not-be-created" / "nested"
            with self.assertRaisesRegex(ValueError, "inside the repository root"):
                write_release_notes(root, "2.1.0", outside_parent / "notes.md")
            with self.assertRaisesRegex(ValueError, "special path components"):
                write_release_notes(root, "2.1.0", root / "release-bundle" / ".." / "alternate.md")
            for alias, suffix in {
                ".git.": Path("hooks") / "pre-commit",
                ".git ": Path("hooks") / "pre-commit",
                ".github.": Path("workflows") / "release.yml",
                ".github ": Path("workflows") / "release.yml",
            }.items():
                with self.subTest(alias=alias), self.assertRaisesRegex(ValueError, "special path components"):
                    write_release_notes(root, "2.1.0", root / alias / suffix)
            with self.assertRaisesRegex(ValueError, "special path components"):
                write_release_notes(root, "2.1.0", root / "RELEASE_NOTES.md:alternate")
            with self.assertRaisesRegex(ValueError, "special path components"):
                write_release_notes(root, "2.1.0", root / "NUL")
            with self.assertRaisesRegex(ValueError, "reserved repository components"):
                write_release_notes(root, "2.1.0", root / ".git" / "hooks" / "pre-commit")
            with self.assertRaisesRegex(ValueError, "reserved repository components"):
                write_release_notes(root, "2.1.0", root / ".github" / "workflows" / "release.yml")

            nested = root / "release-bundle" / "notes" / "RELEASE_NOTES.md"
            written = write_release_notes(root, "2.1.0", nested)

            self.assertEqual(existing.read_text(encoding="utf-8"), "preserve")
            self.assertFalse((root.parent / "outside.md").exists())
            self.assertFalse(outside_parent.exists())
            self.assertEqual(written, nested)
            self.assertEqual(
                nested.read_text(encoding="utf-8"),
                "## [2.1.0] - 2026-07-26\n\n- Deterministic notes.\n",
            )

    def test_release_notes_rejects_in_root_symlink_output_parent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            (root / "CHANGELOG.md").write_text(
                """# Changelog

## [2.1.0] - 2026-07-26

- Deterministic notes.
""",
                encoding="utf-8",
            )
            hook = root / ".git" / "hooks" / "pre-commit"
            hook.parent.mkdir(parents=True)
            link = root / "release-output"
            try:
                os.symlink(hook.parent, link, target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            with self.assertRaisesRegex(ValueError, "symlinks or junctions"):
                write_release_notes(root, "2.1.0", link / hook.name)

            self.assertFalse(hook.exists())

    def test_release_notes_allows_a_symlinked_repository_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            actual = base / "actual"
            actual.mkdir()
            (actual / "CHANGELOG.md").write_text(
                """# Changelog

## [2.1.0] - 2026-07-26

- Deterministic notes.
""",
                encoding="utf-8",
            )
            root = base / "repo"
            try:
                os.symlink(actual, root, target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            written = write_release_notes(root, "2.1.0", root / "RELEASE_NOTES.md")

            self.assertEqual(written, actual / "RELEASE_NOTES.md")
            self.assertEqual(
                written.read_text(encoding="utf-8"),
                "## [2.1.0] - 2026-07-26\n\n- Deterministic notes.\n",
            )

    @unittest.skipUnless(os.name == "nt", "Windows junctions only")
    def test_release_notes_rejects_in_root_junction_output_parent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            (root / "CHANGELOG.md").write_text(
                """# Changelog

## [2.1.0] - 2026-07-26

- Deterministic notes.
""",
                encoding="utf-8",
            )
            (root / "pyproject.toml").write_text(
                '[project]\nname = "ai-dememory"\nversion = "2.1.0"\n',
                encoding="utf-8",
            )
            hook = root / ".git" / "hooks" / "pre-commit"
            hook.parent.mkdir(parents=True)
            junction = root / "release-output"
            created = subprocess.run(
                ["cmd", "/d", "/c", "mklink", "/J", str(junction), str(hook.parent)],
                capture_output=True,
                text=True,
                check=False,
            )
            if created.returncode != 0:
                self.skipTest(f"junction creation unavailable: {created.stderr or created.stdout}")
            try:
                stderr = io.StringIO()
                with redirect_stderr(stderr):
                    self.assertEqual(
                        release_guard_main(
                            [
                                "--root",
                                str(root),
                                "--tag",
                                "v2.1.0",
                                "--version-only",
                                "--release-notes",
                                str(Path(junction.name) / hook.name),
                            ]
                        ),
                        1,
                    )

                self.assertIn("symlinks or junctions", stderr.getvalue())
                self.assertFalse(hook.exists())
            finally:
                if junction.exists():
                    os.rmdir(junction)

    @unittest.skipUnless(os.name == "nt", "Windows 8.3 aliases only")
    def test_release_notes_cli_rejects_reserved_windows_short_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            (root / "CHANGELOG.md").write_text(
                """# Changelog

## [2.1.0] - 2026-07-26

- Deterministic notes.
""",
                encoding="utf-8",
            )
            (root / "pyproject.toml").write_text(
                '[project]\nname = "ai-dememory"\nversion = "2.1.0"\n',
                encoding="utf-8",
            )
            protected_paths = {
                root / ".git": Path("hooks") / "pre-commit",
                root / ".github": Path("workflows") / "new-release.yml",
            }
            aliases: list[tuple[str, Path]] = []
            for protected, suffix in protected_paths.items():
                (protected / suffix.parent).mkdir(parents=True)
                buffer = ctypes.create_unicode_buffer(32768)
                size = ctypes.windll.kernel32.GetShortPathNameW(str(protected), buffer, len(buffer))
                if not size or size >= len(buffer):
                    continue
                alias = Path(buffer.value).name
                if alias and alias.casefold() != protected.name.casefold():
                    aliases.append((alias, suffix))
            if not aliases:
                self.skipTest("Windows 8.3 aliases are unavailable")

            for alias, suffix in aliases:
                with self.subTest(alias=alias):
                    stderr = io.StringIO()
                    with redirect_stderr(stderr):
                        self.assertEqual(
                            release_guard_main(
                                [
                                    "--root",
                                    str(root),
                                    "--tag",
                                    "v2.1.0",
                                    "--version-only",
                                    "--release-notes",
                                    str(Path(alias) / suffix),
                                ]
                            ),
                            1,
                        )
                    self.assertIn("reserved repository components", stderr.getvalue())

            self.assertFalse((root / ".git" / "hooks" / "pre-commit").exists())
            self.assertFalse((root / ".github" / "workflows" / "new-release.yml").exists())

    def test_release_workflow_bundles_notes_before_using_them(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
        generate = "--release-notes RELEASE_NOTES.md"
        create = 'gh release create "$RELEASE_TAG"'

        self.assertLess(workflow.index(generate), workflow.index(create))
        self.assertIn("sha256sum dist/* RELEASE_NOTES.md", workflow)
        self.assertIn("test -s release-bundle/RELEASE_NOTES.md", workflow)
        self.assertIn("--notes-file release-bundle/RELEASE_NOTES.md", workflow)
        self.assertNotIn("--generate-notes", workflow)

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

