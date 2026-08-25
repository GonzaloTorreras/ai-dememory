from __future__ import annotations

import math
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from config_file import (  # noqa: E402
    CONFIG_NAME,
    ConfigError,
    load_config_path,
    parse_config_text,
    set_section,
    set_section_path,
)


class StrictMainConfigTests(unittest.TestCase):
    def test_checked_in_template_parses_to_flat_sections(self) -> None:
        parsed = parse_config_text(
            (ROOT / "vault-template" / CONFIG_NAME).read_text(encoding="utf-8")
        )

        self.assertEqual(parsed["memory"]["schema_version"], "2.0")
        self.assertEqual(parsed["recall"]["clients"], ["codex", "claude"])
        self.assertEqual(parsed["providers.codex"]["capture_raw"], False)
        self.assertNotIn("providers", parsed)

    def test_missing_empty_and_partial_configs_are_supported(self) -> None:
        self.assertEqual(parse_config_text(""), {})
        self.assertEqual(parse_config_text("# intentionally empty\n"), {})
        self.assertEqual(parse_config_text("[recall]\n"), {"recall": {}})
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.assertEqual(load_config_path(root / "missing.toml", root=root), {})

    def test_all_current_provider_names_are_allowed_but_unknown_names_are_not(self) -> None:
        text = "".join(
            f"[providers.{name}]\nenabled = false\n"
            for name in ("codex", "claude", "chatgpt", "cursor", "windsurf")
        )
        parsed = parse_config_text(text)
        self.assertEqual(len(parsed), 5)

        with self.assertRaises(ConfigError) as raised:
            parse_config_text("[providers.unlisted]\nenabled = false\n")
        self.assertEqual(raised.exception.code, "unknown_provider")
        self.assertEqual(raised.exception.field, "providers.<unknown>")

    def test_top_level_keys_unknown_sections_subsections_and_keys_are_rejected(self) -> None:
        cases = (
            ("version = 1\n", "top_level_key", "<unknown>"),
            ("[unknown]\nenabled = true\n", "unknown_section", "<unknown>"),
            ("[recall.extra]\nenabled = true\n", "unknown_subsection", "recall.<unknown>"),
            ("[recall]\nunexpected = true\n", "unknown_key", "recall.<unknown>"),
        )
        for text, code, field in cases:
            with self.subTest(code=code):
                with self.assertRaises(ConfigError) as raised:
                    parse_config_text(text)
                self.assertEqual(raised.exception.code, code)
                self.assertEqual(raised.exception.field, field)
                self.assertIsNotNone(raised.exception.line)
                self.assertIsNotNone(raised.exception.column)

    def test_unknown_diagnostic_fields_never_reflect_quoted_or_multiline_keys(self) -> None:
        key_canary = "DO_NOT_ECHO_UNKNOWN_CONFIG_KEY"
        forged_line = "FORGED_CONFIG_DIAGNOSTIC_LINE"
        cases = (
            (
                f'[review]\n"{key_canary}\\n{forged_line}" = true\n',
                "main",
                "review.<unknown>",
            ),
            (
                f'[providers."{key_canary}\\n{forged_line}"]\nenabled = true\n',
                "main",
                "providers.<unknown>",
            ),
            (
                f'[false_positives."{key_canary}\\n{forged_line}"]\nignored = true\n',
                "review_state",
                "false_positives.<unsafe-id>",
            ),
        )
        for text, config_kind, expected_field in cases:
            with self.subTest(config_kind=config_kind, expected_field=expected_field):
                with self.assertRaises(ConfigError) as raised:
                    parse_config_text(text, config_kind=config_kind)
                self.assertEqual(raised.exception.field, expected_field)
                self.assertNotIn(key_canary, str(raised.exception))
                self.assertNotIn(forged_line, str(raised.exception))
                self.assertNotIn("\n", str(raised.exception))

    def test_structural_types_are_exact_and_arrays_contain_only_strings(self) -> None:
        cases = (
            ("[recall]\nenabled = 1\n", "recall.enabled"),
            ("[recall]\ndefault_budget_tokens = true\n", "recall.default_budget_tokens"),
            ("[recall]\nclients = [\"codex\", 1]\n", "recall.clients"),
            ("[review]\nupdated_at = 2026-08-26\n", "review.updated_at"),
        )
        for text, field in cases:
            with self.subTest(field=field):
                with self.assertRaises(ConfigError) as raised:
                    parse_config_text(text)
                self.assertEqual(raised.exception.code, "invalid_type")
                self.assertEqual(raised.exception.field, field)

    def test_finite_numbers_are_accepted_and_non_finite_numbers_are_rejected(self) -> None:
        parsed = parse_config_text("[recall]\nmin_relevance_score = 0.25\n")
        self.assertEqual(parsed["recall"]["min_relevance_score"], 0.25)

        for value in ("inf", "+inf", "-inf", "nan"):
            with self.subTest(value=value):
                with self.assertRaises(ConfigError) as raised:
                    parse_config_text(f"[recall]\nmin_relevance_score = {value}\n")
                self.assertEqual(raised.exception.code, "non_finite_number")
                self.assertTrue(math.isfinite(0.0))

    def test_syntax_and_duplicate_diagnostics_redact_raw_values(self) -> None:
        redaction_canary = "do-not-echo-this-value"
        with self.assertRaises(ConfigError) as syntax:
            parse_config_text(
                f"[review]\nreviewer = {redaction_canary}\n",
                source="fixture.toml",
            )
        self.assertEqual(syntax.exception.code, "toml_syntax")
        self.assertEqual(syntax.exception.source, "fixture.toml")
        self.assertNotIn(redaction_canary, str(syntax.exception))

        with self.assertRaises(ConfigError) as duplicate:
            parse_config_text("[recall]\nenabled = true\nenabled = false\n")
        self.assertEqual(duplicate.exception.code, "duplicate_definition")
        self.assertIsNotNone(duplicate.exception.line)
        self.assertNotIn("true", str(duplicate.exception))
        self.assertNotIn("false", str(duplicate.exception))


class StrictReviewStateTests(unittest.TestCase):
    def test_review_state_accepts_known_record_and_recommendation_fields(self) -> None:
        parsed = parse_config_text(
            """
[false_positives.fp_0123456789abcdef]
ignored = true
reason = "reviewed"
reviewer = "Unit Test"
reviewed_at = "2026-08-26"
review_after = "2026-11-24"
recommendation_id = "rec_safe"
recommendation_path = "inbox/recommendation.md"
recommendation_action = "ignore_false_positive"
recommendation_policy_violation = false

[conflicts.conf_fedcba9876543210]
status = "resolved"
decision = "keep:mem_one"
proposal_path = "inbox/conflict-resolution/proposal.md"
reviewer = "Unit Test"
reviewed_at = "2026-08-26"
""",
            config_kind="review_state",
        )

        self.assertTrue(parsed["false_positives.fp_0123456789abcdef"]["ignored"])
        self.assertEqual(parsed["conflicts.conf_fedcba9876543210"]["status"], "resolved")

    def test_review_state_rejects_dotted_or_unsafe_ids(self) -> None:
        for header in (
            '[false_positives."fp.dotted"]',
            '[false_positives."../escape"]',
            "[false_positives.fp_safe]",
            '[conflicts."conf space"]',
            "[conflicts.conf_123]",
        ):
            with self.subTest(header=header):
                with self.assertRaises(ConfigError) as raised:
                    parse_config_text(
                        f"{header}\nreviewer = \"Unit Test\"\n",
                        config_kind="review_state",
                    )
                self.assertEqual(raised.exception.code, "unsafe_identifier")

    def test_review_state_rejects_unknown_namespaces_fields_and_types(self) -> None:
        cases = (
            ("[other.id]\nreviewer = \"x\"\n", "unknown_section"),
            ("[false_positives.fp_0123456789abcdef]\nunexpected = \"x\"\n", "unknown_key"),
            ("[conflicts.conf_fedcba9876543210]\nstatus = false\n", "invalid_type"),
        )
        for text, code in cases:
            with self.subTest(code=code):
                with self.assertRaises(ConfigError) as raised:
                    parse_config_text(text, config_kind="review_state")
                self.assertEqual(raised.exception.code, code)


class StrictConfigWriterTests(unittest.TestCase):
    def test_writer_validates_existing_and_candidate_before_atomic_write(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / CONFIG_NAME
            original = "[recall]\nunexpected = true\n"
            path.write_text(original, encoding="utf-8")

            with self.assertRaises(ConfigError) as existing_error:
                set_section(root, "review", {"mode": "strict"})
            self.assertEqual(existing_error.exception.code, "unknown_key")
            self.assertEqual(path.read_text(encoding="utf-8"), original)

            path.write_text("[review]\nmode = \"strict\"\n", encoding="utf-8")
            before_candidate = path.read_text(encoding="utf-8")
            with self.assertRaises(ConfigError) as candidate_error:
                set_section(root, "review", {"unknown": "value"})
            self.assertEqual(candidate_error.exception.code, "unknown_key")
            self.assertEqual(path.read_text(encoding="utf-8"), before_candidate)

    def test_writer_escapes_strings_and_reparses_the_candidate(self) -> None:
        reviewer = 'line one\nline two with "quotes" and \\slashes'
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            set_section(root, "review", {"reviewer": reviewer, "mode": "strict"})
            loaded = load_config_path(root / CONFIG_NAME, root=root)

        self.assertEqual(loaded["review"]["reviewer"], reviewer)

    def test_writer_refuses_equivalent_header_spelling_it_cannot_replace(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / CONFIG_NAME
            original = '["review"]\nmode = "strict"\n'
            path.write_text(original, encoding="utf-8")

            with self.assertRaises(ConfigError) as raised:
                set_section(root, "review", {"mode": "advisory"})

            self.assertEqual(raised.exception.code, "unsupported_header_spelling")
            self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_writer_stops_at_any_valid_following_table_header(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / CONFIG_NAME
            path.write_text(
                '[review]\nmode = "strict"\n\n["recall"] # preserved\nenabled = true\n',
                encoding="utf-8",
            )

            set_section(root, "review", {"mode": "advisory"})
            updated = path.read_text(encoding="utf-8")

        self.assertIn('["recall"] # preserved\nenabled = true', updated)
        self.assertEqual(parse_config_text(updated)["review"]["mode"], "advisory")

    def test_review_state_writer_requires_its_explicit_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / ".ai-dememory-ignore.toml"
            set_section_path(
                path,
                "false_positives.fp_0123456789abcdef",
                {"ignored": True, "reviewer": "Unit Test"},
                root=root,
                config_kind="review_state",
            )
            loaded = load_config_path(path, root=root, config_kind="review_state")

        self.assertTrue(loaded["false_positives.fp_0123456789abcdef"]["ignored"])


if __name__ == "__main__":
    unittest.main()
