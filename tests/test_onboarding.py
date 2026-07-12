from __future__ import annotations

import json
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from onboarding import apply_onboarding, main as onboarding_main, onboarding_plan  # noqa: E402
from validate_memory import validate_repo_result  # noqa: E402


def answers() -> dict[str, object]:
    return {
        "reviewed_by": "Unit Test Reviewer",
        "values": ["Prefer clear, safe work."],
        "preferences": ["Use narrow tests before the full suite."],
        "recommendations": ["Search project memory before non-trivial work."],
        "projects": [
            {
                "name": "portfolio-tracker",
                "paths": ["D:/Github/portfolio-tracker"],
                "aliases": ["portfolio"],
                "keywords": ["thesis", "staging"],
            }
        ],
        "clients": ["codex", "claude"],
        "recall": {"default_budget_tokens": 900, "baseline_budget_tokens": 300},
        "learning": {"session_proposals": True},
    }


def apply_reviewed(root: Path, payload: dict[str, object]) -> dict[str, object]:
    plan = onboarding_plan(root, payload)
    return apply_onboarding(root, payload, str(plan["plan_sha256"]))


class OnboardingTests(unittest.TestCase):
    def test_preview_is_side_effect_free_and_complete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = onboarding_plan(root, answers())

            self.assertFalse((root / "memories").exists())
            self.assertFalse((root / ".ai-dememory.toml").exists())

        self.assertTrue(plan["can_apply"])
        self.assertEqual(plan["created_count"], 5)
        self.assertTrue(all(item["status"] == "create" for item in plan["writes"]))
        self.assertFalse(plan["writes_files"])

    def test_apply_writes_reviewed_valid_memory_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = apply_reviewed(root, answers())
            second = apply_reviewed(root, answers())
            validation = validate_repo_result(root)
            values_text = (root / "memories/durable/onboarding-values.md").read_text(encoding="utf-8")
            config_text = (root / ".ai-dememory.toml").read_text(encoding="utf-8")

        self.assertTrue(first["applied"])
        self.assertEqual(len(first["changed"]), 5)
        self.assertEqual(second["changed"], [])
        self.assertEqual(second["unchanged_count"], 5)
        self.assertTrue(validation["ok"], validation)
        self.assertIn("reviewed: true", values_text)
        self.assertIn('reviewed_by: "Unit Test Reviewer"', values_text)
        self.assertIn("[recall]", config_text)
        self.assertIn("per_turn = true", config_text)
        self.assertIn("[learning]", config_text)
        self.assertIn("session_proposals = true", config_text)

    def test_existing_memory_conflict_refuses_all_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "memories/durable/onboarding-values.md"
            path.parent.mkdir(parents=True)
            path.write_text("existing reviewed memory", encoding="utf-8")
            plan = onboarding_plan(root, answers())
            with self.assertRaisesRegex(ValueError, "conflicts"):
                apply_reviewed(root, answers())

            self.assertFalse((root / "memories/durable/onboarding-preferences.md").exists())

        self.assertEqual(plan["conflict_count"], 1)
        self.assertFalse(plan["can_apply"])

    def test_secret_like_answer_is_rejected_before_write(self) -> None:
        secret_answers = answers()
        secret_answers["recommendations"] = ["Use token sk-proj-" + ("x" * 40)]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(ValueError, "secret scan"):
                apply_reviewed(root, secret_answers)
            self.assertFalse((root / "memories").exists())

    def test_project_paths_cannot_escape_and_output_is_json_serializable(self) -> None:
        escaped = answers()
        escaped["projects"] = [{"name": "../outside"}]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = onboarding_plan(root, escaped)
            serialized = json.dumps(plan)

        self.assertIn("memories/projects/outside.md", serialized)
        self.assertNotIn("../outside.md", serialized)

    def test_duplicate_normalized_project_slugs_are_rejected(self) -> None:
        duplicate = answers()
        duplicate["projects"] = [{"name": "Portfolio Tracker"}, {"name": "portfolio-tracker"}]
        with tempfile.TemporaryDirectory() as tmp, self.assertRaisesRegex(ValueError, "unique normalized slugs"):
            onboarding_plan(Path(tmp), duplicate)

    def test_plain_preview_prints_fingerprint_and_apply_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = onboarding_main(
                    [
                        "--root", tmp, "--reviewed-by", "Unit Test", "--value", "Prefer safe work.",
                        "--preference", "Run tests.", "--recommendation", "Recall reviewed memory.",
                    ]
                )

        self.assertEqual(exit_code, 0)
        self.assertIn("plan_sha256:", output.getvalue())
        self.assertIn("--apply --expect-plan-sha256", output.getvalue())

    def test_apply_requires_matching_preview_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as other_tmp:
            root = Path(tmp)
            plan = onboarding_plan(root, answers())
            changed = answers()
            changed["values"] = ["Changed after preview."]
            with self.assertRaisesRegex(ValueError, "changed after preview"):
                apply_onboarding(root, changed, str(plan["plan_sha256"]))
            with self.assertRaisesRegex(ValueError, "required"):
                apply_onboarding(root, answers())
            with self.assertRaisesRegex(ValueError, "changed after preview"):
                apply_onboarding(Path(other_tmp), answers(), str(plan["plan_sha256"]))
            self.assertFalse((root / "memories").exists())
            self.assertFalse((Path(other_tmp) / "memories").exists())

    def test_apply_rolls_back_when_batch_commit_fails(self) -> None:
        real_replace = os.replace
        calls = 0

        def fail_second(source: object, target: object) -> None:
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("simulated Windows file lock")
            real_replace(source, target)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = onboarding_plan(root, answers())
            with patch("onboarding.os.replace", side_effect=fail_second), self.assertRaisesRegex(OSError, "file lock"):
                apply_onboarding(root, answers(), str(plan["plan_sha256"]))

            self.assertFalse((root / ".ai-dememory.toml").exists())
            self.assertEqual(list((root / "memories").rglob("*.md")), [])

    def test_incomplete_rollback_is_reported_for_manual_recovery(self) -> None:
        real_replace = os.replace
        real_unlink = Path.unlink
        replace_calls = 0

        def fail_second_replace(source: object, target: object) -> None:
            nonlocal replace_calls
            replace_calls += 1
            if replace_calls == 2:
                raise OSError("simulated commit lock")
            real_replace(source, target)

        def fail_canonical_unlink(path: Path, *args: object, **kwargs: object) -> None:
            if path.name == "onboarding-values.md":
                raise OSError("simulated rollback lock")
            real_unlink(path, *args, **kwargs)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = onboarding_plan(root, answers())
            with patch("onboarding.os.replace", side_effect=fail_second_replace), patch(
                "onboarding.Path.unlink", autospec=True, side_effect=fail_canonical_unlink
            ), self.assertRaisesRegex(RuntimeError, "rollback incomplete"):
                apply_onboarding(root, answers(), str(plan["plan_sha256"]))

            self.assertTrue((root / "memories/durable/onboarding-values.md").exists())


if __name__ == "__main__":
    unittest.main()
