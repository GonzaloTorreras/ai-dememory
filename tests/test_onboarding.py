from __future__ import annotations

import hashlib
import json
import io
import os
from pathlib import Path
import sys
import tempfile
import tomllib
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
PINNED_TEST_IMAGE = "registry.example/ai-dememory@sha256:" + ("a" * 64)
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import onboarding  # noqa: E402
from onboarding import apply_onboarding, main as onboarding_main, onboarding_plan  # noqa: E402
from resource_policy import resolved_resource_policy  # noqa: E402
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
        "automation": {"intensity": "balanced", "model_policy": "proposals"},
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

    def test_preview_rejects_nonfinite_relevance_thresholds(self) -> None:
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as tmp:
                payload = answers()
                payload["recall"] = {
                    **dict(payload["recall"]),
                    "min_relevance_score": value,
                }
                with self.assertRaisesRegex(ValueError, "number must be between"):
                    onboarding_plan(Path(tmp), payload)

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
        self.assertIn("[resources]", config_text)
        self.assertIn("[automation]", config_text)
        self.assertIn('model_policy = "proposals"', config_text)

    def test_enabled_schedule_receipt_blocks_wizard_apply_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / ".ai-dememory.toml"
            original = (
                "[schedule]\n"
                "enabled = true\n"
                'task_namespace = "ai-dememory-vault-1234567890"\n'
                'plan_sha256 = "' + ("a" * 64) + '"\n'
            )
            config_path.write_text(original, encoding="utf-8")

            plan = onboarding_plan(root, answers())
            with self.assertRaisesRegex(ValueError, "enabled-schedule"):
                apply_onboarding(root, answers(), str(plan["plan_sha256"]))
            current = config_path.read_text(encoding="utf-8")

        self.assertTrue(plan["schedule_preserved"])
        self.assertFalse(plan["can_apply"])
        self.assertIn(".ai-dememory.toml:[enabled-schedule]", plan["conflicts"])
        self.assertEqual(current, original)

    def test_profiles_are_bounded_zero_model_call_plans(self) -> None:
        minimal = answers()
        minimal["automation"] = {"intensity": "minimal", "model_policy": "off"}
        minimal["learning"] = {"session_proposals": False}
        active = answers()
        active["automation"] = {"intensity": "active", "model_policy": "proposals"}
        active.pop("recall", None)

        with tempfile.TemporaryDirectory() as tmp:
            minimal_plan = onboarding_plan(Path(tmp), minimal)
        with tempfile.TemporaryDirectory() as tmp:
            active_plan = onboarding_plan(Path(tmp), active)

        minimal_policy = minimal_plan["resource_policy"]
        active_policy = active_plan["resource_policy"]
        self.assertEqual(minimal_policy["estimated_local_runs_per_week"], 1)
        self.assertEqual(minimal_policy["automatic_recall_max_tokens_per_eligible_turn"], 0)
        self.assertEqual(minimal_policy["resources"]["provider_file_limit"], 5)
        self.assertEqual(minimal_policy["resources"]["mcp_idle_timeout_seconds"], 120)
        self.assertEqual(minimal_policy["runtime_model_calls_per_maintenance_run"], 0)
        self.assertEqual(minimal_policy["runtime_embedding_calls_per_maintenance_run"], 0)
        self.assertEqual(active_policy["estimated_local_runs_per_week"], 8)
        self.assertEqual(active_policy["automatic_recall_max_tokens_per_eligible_turn"], 2400)
        self.assertEqual(active_policy["resources"]["provider_file_limit"], 50)
        self.assertEqual(active_policy["resources"]["mcp_idle_timeout_seconds"], 1800)
        self.assertFalse(active_policy["host_model"]["durable_auto_promotion"])

    def test_integration_configs_are_vault_bound_and_server_enforced(self) -> None:
        payload = answers()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = onboarding_plan(root, payload)

        integrations = plan["integrations"]
        codex = tomllib.loads(integrations["mcp_configs"]["codex"])["mcp_servers"]["ai-dememory"]
        claude = integrations["mcp_configs"]["claude"]["mcpServers"]["ai-dememory"]
        codex_hook = integrations["hook_configs"]["codex"]["hooks"]["UserPromptSubmit"][0]["hooks"][0]
        self.assertTrue(integrations["vault_bound"])
        self.assertEqual(codex["env"]["AI_DEMEMORY_ROOT"], str(root.resolve()))
        self.assertEqual(codex["args"][-3:], ["--profile", "core", "--require-bound-root"])
        self.assertIn(["--idle-timeout-seconds", "600"], [codex["args"][index : index + 2] for index in range(len(codex["args"]) - 1)])
        self.assertEqual(claude["env"]["AI_DEMEMORY_ROOT"], str(root.resolve()))
        self.assertEqual(claude["args"][-3:], ["--profile", "core", "--require-bound-root"])
        self.assertIn("--public-only", codex_hook["command"])
        self.assertIn(str(root.resolve()), codex_hook["command"])

    def test_docker_schedule_preview_requires_and_preserves_immutable_image(self) -> None:
        payload = answers()
        payload["schedule"] = {"mode": "docker", "image": PINNED_TEST_IMAGE}
        with tempfile.TemporaryDirectory() as tmp:
            plan = onboarding_plan(Path(tmp), payload)

        command = plan["integrations"]["schedule_plan_command"]
        self.assertTrue(plan["resource_policy"]["scheduler_image_immutable"])
        self.assertTrue(plan["integrations"]["scheduler_image_immutable"])
        self.assertEqual(command[command.index("--image") + 1], PINNED_TEST_IMAGE)

        payload["schedule"] = {"mode": "docker", "image": "ai-dememory:latest"}
        with tempfile.TemporaryDirectory() as tmp, self.assertRaisesRegex(ValueError, "immutable"):
            onboarding_plan(Path(tmp), payload)

    def test_session_proposals_require_proposals_model_policy(self) -> None:
        contradictory = answers()
        contradictory["automation"] = {"intensity": "balanced", "model_policy": "off"}
        with tempfile.TemporaryDirectory() as tmp, self.assertRaisesRegex(
            ValueError,
            "model_policy=proposals",
        ):
            onboarding_plan(Path(tmp), contradictory)

    def test_invalid_resource_override_fails_closed_to_profile_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".ai-dememory.toml").write_text(
                "\n".join(
                    [
                        "[automation]",
                        'intensity = "minimal"',
                        'model_policy = "off"',
                        "",
                        "[resources]",
                        "provider_file_limit = 999",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            policy = resolved_resource_policy(root)

        self.assertFalse(policy["valid"])
        self.assertEqual(policy["intensity"], "minimal")
        self.assertEqual(policy["resources"]["provider_file_limit"], 5)
        self.assertTrue(
            any("provider_file_limit" in error for error in policy["validation_errors"])
        )

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
        self.assertIn("MCP profile/idle lease:", output.getvalue())
        self.assertIn("Provider/maintenance ceilings:", output.getvalue())

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

    def test_apply_rejects_config_drift_after_fingerprint_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = onboarding_plan(root, answers())
            real_batch_write = onboarding.atomic_batch_write

            def drift_then_write(batch: object) -> None:
                (root / ".ai-dememory.toml").write_text(
                    "[external]\nchanged = true\n",
                    encoding="utf-8",
                )
                real_batch_write(batch)  # type: ignore[arg-type]

            with patch(
                "onboarding.atomic_batch_write",
                side_effect=drift_then_write,
            ), self.assertRaisesRegex(ValueError, "changed after review"):
                apply_onboarding(root, answers(), str(plan["plan_sha256"]))

            self.assertEqual(
                (root / ".ai-dememory.toml").read_text(encoding="utf-8"),
                "[external]\nchanged = true\n",
            )
            self.assertFalse((root / "memories").exists())

    def test_existing_crlf_config_uses_exact_byte_precondition(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / ".ai-dememory.toml"
            original = b"[legacy]\r\nenabled = true\r\n"
            config_path.write_bytes(original)
            plan = onboarding_plan(root, answers())
            config_write = next(
                item for item in plan["writes"] if item["path"] == ".ai-dememory.toml"
            )

            result = apply_onboarding(root, answers(), str(plan["plan_sha256"]))
            updated = config_path.read_text(encoding="utf-8")

        self.assertEqual(config_write["current_sha256"], hashlib.sha256(original).hexdigest())
        self.assertIn("[legacy]", updated)
        self.assertIn("[recall]", updated)
        self.assertIn(".ai-dememory.toml", result["changed"])

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
