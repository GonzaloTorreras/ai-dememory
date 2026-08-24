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
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

from ai_dememory_tool import __version__ as PACKAGE_VERSION
from ai_dememory_tool import cli as unified_cli
from ai_dememory_tool.vault_binding import VaultBinding, VaultBindingError


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
PINNED_TEST_IMAGE = "registry.example/ai-dememory@sha256:" + ("a" * 64)
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import onboarding  # noqa: E402
from command_render import render_copy_command  # noqa: E402
from onboarding import (  # noqa: E402
    apply_onboarding,
    apply_operational_setup,
    main as onboarding_main,
    onboarding_plan,
    operational_setup_plan,
)
from resource_policy import resolved_resource_policy  # noqa: E402
from setup_plan import setup_plan  # noqa: E402
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
    }


def apply_reviewed(root: Path, payload: dict[str, object]) -> dict[str, object]:
    plan = onboarding_plan(root, payload)
    return apply_onboarding(root, payload, str(plan["plan_sha256"]))


def operational_answers() -> dict[str, object]:
    return {
        "clients": ["codex", "claude"],
        "automation": {"intensity": "balanced", "model_policy": "off"},
        "learning": {"session_proposals": False},
    }


def apply_operational(root: Path, payload: dict[str, object]) -> dict[str, object]:
    plan = operational_setup_plan(root, payload)
    return apply_operational_setup(root, payload, str(plan["plan_sha256"]))


def operational_main(argv: list[str]) -> int:
    return onboarding_main(argv, mode="operational")


class InteractiveStdin:
    def isatty(self) -> bool:
        return True


class OnboardingTests(unittest.TestCase):
    def setUp(self) -> None:
        # Keep rootless setup/onboard tests independent of a developer's local
        # default-vault selector.
        self._default_selector_home = tempfile.TemporaryDirectory()
        self._default_selector_patch = patch.dict(
            os.environ,
            {"AI_DEMEMORY_CONFIG_HOME": self._default_selector_home.name},
            clear=False,
        )
        self._default_selector_patch.start()
        self.addCleanup(self._default_selector_home.cleanup)
        self.addCleanup(self._default_selector_patch.stop)

    def test_preview_is_side_effect_free_and_complete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = onboarding_plan(root, answers())

            self.assertFalse((root / "memories").exists())
            self.assertFalse((root / ".ai-dememory.toml").exists())

        self.assertTrue(plan["can_apply"])
        self.assertEqual(plan["created_count"], 4)
        self.assertFalse(plan["writes_config"])
        self.assertNotIn("resource_policy", plan)
        self.assertNotIn("integrations", plan)
        self.assertTrue(all(item["status"] == "create" for item in plan["writes"]))
        self.assertFalse(plan["writes_files"])

    def test_onboarding_rejects_operational_payload_fields(self) -> None:
        payload = answers()
        payload["automation"] = {"intensity": "minimal"}
        with tempfile.TemporaryDirectory() as tmp, self.assertRaisesRegex(
            ValueError,
            "setup wizard",
        ):
            onboarding_plan(Path(tmp), payload)

    def test_preview_rejects_nonfinite_relevance_thresholds(self) -> None:
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as tmp:
                payload = operational_answers()
                payload["recall"] = {
                    "min_relevance_score": value,
                }
                with self.assertRaisesRegex(ValueError, "number must be between"):
                    operational_setup_plan(Path(tmp), payload)

    def test_apply_writes_reviewed_valid_memory_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = apply_reviewed(root, answers())
            second = apply_reviewed(root, answers())
            validation = validate_repo_result(root)
            values_text = (root / "memories/durable/onboarding-values.md").read_text(encoding="utf-8")
            config_exists = (root / ".ai-dememory.toml").exists()

        self.assertTrue(first["applied"])
        self.assertEqual(len(first["changed"]), 4)
        self.assertEqual(second["changed"], [])
        self.assertEqual(second["unchanged_count"], 4)
        self.assertTrue(validation["ok"], validation)
        self.assertFalse(config_exists)
        self.assertIn("reviewed: true", values_text)
        self.assertIn('reviewed_by: "Unit Test Reviewer"', values_text)

    def test_operational_setup_apply_writes_only_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = apply_operational(root, operational_answers())
            second = apply_operational(root, operational_answers())
            config_text = (root / ".ai-dememory.toml").read_text(encoding="utf-8")

            self.assertFalse((root / "memories").exists())

        self.assertEqual(first["changed"], [".ai-dememory.toml"])
        self.assertEqual(second["changed"], [])
        self.assertTrue(first["writes_config"])
        self.assertFalse(first["durable_memory_reviewed"])
        self.assertIn("[recall]", config_text)
        self.assertIn("[resources]", config_text)
        self.assertIn('intensity = "balanced"', config_text)
        self.assertIn('model_policy = "off"', config_text)

    def test_enabled_schedule_receipt_blocks_operational_setup_without_overwrite(self) -> None:
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

            plan = operational_setup_plan(root, operational_answers())
            with self.assertRaisesRegex(ValueError, "enabled-schedule"):
                apply_operational_setup(root, operational_answers(), str(plan["plan_sha256"]))
            current = config_path.read_text(encoding="utf-8")

        self.assertTrue(plan["schedule_preserved"])
        self.assertFalse(plan["can_apply"])
        self.assertIn(".ai-dememory.toml:[enabled-schedule]", plan["conflicts"])
        self.assertEqual(current, original)

    def test_onboarding_never_rewrites_existing_operational_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / ".ai-dememory.toml"
            original = "[automation]\nintensity = \"minimal\"\nmodel_policy = \"off\"\n"
            config_path.write_text(original, encoding="utf-8")

            result = apply_reviewed(root, answers())

            self.assertEqual(config_path.read_text(encoding="utf-8"), original)
            self.assertNotIn(".ai-dememory.toml", result["changed"])

    def test_profiles_are_bounded_zero_model_call_plans(self) -> None:
        minimal = operational_answers()
        minimal["automation"] = {"intensity": "minimal", "model_policy": "off"}
        minimal["learning"] = {"session_proposals": False}
        active = operational_answers()
        active["automation"] = {"intensity": "active", "model_policy": "proposals"}
        active.pop("recall", None)

        with tempfile.TemporaryDirectory() as tmp:
            minimal_plan = operational_setup_plan(Path(tmp), minimal)
        with tempfile.TemporaryDirectory() as tmp:
            active_plan = operational_setup_plan(Path(tmp), active)

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
        payload = operational_answers()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = operational_setup_plan(root, payload)

        integrations = plan["integrations"]
        codex = tomllib.loads(integrations["mcp_configs"]["codex"])["mcp_servers"]["ai-dememory"]
        claude = integrations["mcp_configs"]["claude"]["mcpServers"]["ai-dememory"]
        codex_hook = integrations["hook_configs"]["codex"]["hooks"]["UserPromptSubmit"][0]["hooks"][0]
        self.assertTrue(integrations["vault_bound"])
        self.assertEqual(integrations["generated_by_version"], PACKAGE_VERSION)
        schedule_command = integrations["schedule_plan_command"]
        self.assertEqual(
            schedule_command[:5],
            ["ai-dememory", "--root", str(root.resolve()), "schedule", "plan"],
        )
        self.assertEqual(schedule_command.count("--root"), 1)
        self.assertEqual(codex["env"]["AI_DEMEMORY_ROOT"], str(root.resolve()))
        self.assertNotIn("--require-version", codex["args"])
        self.assertEqual(codex["args"][-3:], ["--profile", "core", "--require-bound-root"])
        self.assertIn(["--idle-timeout-seconds", "600"], [codex["args"][index : index + 2] for index in range(len(codex["args"]) - 1)])
        self.assertEqual(claude["env"]["AI_DEMEMORY_ROOT"], str(root.resolve()))
        self.assertNotIn("--require-version", claude["args"])
        self.assertEqual(claude["args"][-3:], ["--profile", "core", "--require-bound-root"])
        self.assertIn("--public-only", codex_hook["command"])
        self.assertIn(str(root.resolve()), codex_hook["command"])

    def test_docker_schedule_preview_requires_and_preserves_immutable_image(self) -> None:
        payload = operational_answers()
        payload["schedule"] = {"mode": "docker", "image": PINNED_TEST_IMAGE}
        with tempfile.TemporaryDirectory() as tmp:
            plan = operational_setup_plan(Path(tmp), payload)

        command = plan["integrations"]["schedule_plan_command"]
        self.assertTrue(plan["resource_policy"]["scheduler_image_immutable"])
        self.assertTrue(plan["integrations"]["scheduler_image_immutable"])
        self.assertEqual(command[command.index("--image") + 1], PINNED_TEST_IMAGE)

        payload["schedule"] = {"mode": "docker", "image": "ai-dememory:latest"}
        with tempfile.TemporaryDirectory() as tmp, self.assertRaisesRegex(ValueError, "immutable"):
            operational_setup_plan(Path(tmp), payload)

    def test_session_proposals_require_proposals_model_policy(self) -> None:
        contradictory = operational_answers()
        contradictory["automation"] = {"intensity": "balanced", "model_policy": "off"}
        contradictory["learning"] = {"session_proposals": True}
        with tempfile.TemporaryDirectory() as tmp, self.assertRaisesRegex(
            ValueError,
            "model_policy=proposals",
        ):
            operational_setup_plan(Path(tmp), contradictory)

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
        self.assertIn("Reviewed by: Unit Test", output.getvalue())
        self.assertNotIn("MCP profile/idle lease:", output.getvalue())

    def test_interactive_onboard_collects_only_personal_baseline(self) -> None:
        prompted_answers = [
            "Unit Test Reviewer",
            "Prefer clear, safe work.",
            "Run narrow tests first.",
            "Recall reviewed memory.",
            "",
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = io.StringIO()
            with patch.object(onboarding.sys, "stdin", InteractiveStdin()), patch(
                "builtins.input", side_effect=prompted_answers
            ) as prompt, redirect_stdout(output):
                exit_code = onboarding_main(["--root", tmp])

            self.assertFalse((root / ".ai-dememory.toml").exists())
            self.assertFalse((root / "memories").exists())

        self.assertEqual(exit_code, 0)
        self.assertEqual(prompt.call_count, len(prompted_answers))
        prompt_text = "\n".join(str(call.args[0]) for call in prompt.call_args_list)
        self.assertIn("optional reviewed personal baseline", output.getvalue())
        self.assertIn("Values: principles", output.getvalue())
        self.assertIn("durable baseline only", output.getvalue())
        self.assertIn("--apply --expect-plan-sha256", output.getvalue())
        self.assertNotIn("Intensity [", prompt_text)
        self.assertNotIn("Host-AI policy", prompt_text)

    def test_interactive_onboard_retries_each_missing_required_baseline_field(self) -> None:
        prompted_answers = [
            "",
            "Unit Test Reviewer",
            "",
            "Prefer clear, safe work.",
            "",
            "Run narrow tests first.",
            "",
            "Recall reviewed memory.",
            "",
        ]
        with tempfile.TemporaryDirectory() as tmp:
            output = io.StringIO()
            with patch.object(onboarding.sys, "stdin", InteractiveStdin()), patch(
                "builtins.input", side_effect=prompted_answers
            ) as prompt, redirect_stdout(output):
                exit_code = onboarding_main(["--root", tmp])

        rendered = output.getvalue()
        prompt_text = "\n".join(str(call.args[0]) for call in prompt.call_args_list)
        self.assertEqual(exit_code, 0)
        self.assertEqual(prompt.call_count, len(prompted_answers))
        self.assertIn("Reviewer name is required", rendered)
        self.assertIn("Values is required", rendered)
        self.assertIn("Working preferences is required", rendered)
        self.assertIn("Recommendations for agents is required", rendered)
        self.assertIn("plan_sha256:", rendered)
        self.assertNotIn("Intensity [", prompt_text)
        self.assertNotIn("Host-AI policy", prompt_text)

    def test_operational_setup_rejects_non_object_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, self.assertRaisesRegex(ValueError, "JSON object"):
            operational_setup_plan(Path(tmp), [])  # type: ignore[arg-type]

    def test_guided_wizard_previews_then_applies_operational_answers_once(self) -> None:
        prompted_answers = [
            "",
            "",
            "yes",
            "no",
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = io.StringIO()
            with patch.object(onboarding.sys, "stdin", InteractiveStdin()), patch(
                "builtins.input", side_effect=prompted_answers
            ) as prompt, redirect_stdout(output):
                exit_code = operational_main(["--root", tmp])

            config = (root / ".ai-dememory.toml").read_text(encoding="utf-8")
            memories_exist = (root / "memories").exists()

        self.assertEqual(exit_code, 0)
        self.assertEqual(prompt.call_count, len(prompted_answers))
        self.assertIn("Preview:", output.getvalue())
        self.assertIn("Applied:", output.getvalue())
        self.assertIn("operational vault configuration only", output.getvalue())
        self.assertIn(
            "Optional next actions (setup is complete; nothing else was installed automatically):",
            output.getvalue(),
        )
        self.assertIn("Optional local API for dashboards/scripts, only if you want it", output.getvalue())
        self.assertIn(
            render_copy_command(
                ["ai-dememory", "--root", str(root.resolve()), "api"]
            ),
            output.getvalue(),
        )
        self.assertIn("Optional durable baseline", output.getvalue())
        self.assertIn("setup wizard — operational setup only", output.getvalue())
        self.assertIn("These are ceilings, not jobs", output.getvalue())
        self.assertIn("If you later install a schedule explicitly", output.getvalue())
        self.assertIn("0 model calls and 0 embedding calls", output.getvalue())
        self.assertIn("No local default was recorded", output.getvalue())
        self.assertFalse(memories_exist)
        self.assertIn('intensity = "balanced"', config)

    def test_guided_wizard_explains_catalog_and_never_prompts_for_personal_memory(self) -> None:
        prompted_answers = [
            "active",
            "proposals",
            "n",
            "no",
        ]
        with tempfile.TemporaryDirectory() as tmp:
            output = io.StringIO()
            with patch.object(onboarding.sys, "stdin", InteractiveStdin()), patch(
                "builtins.input", side_effect=prompted_answers
            ) as prompt, redirect_stdout(output):
                exit_code = operational_main(["--root", tmp])

        rendered = output.getvalue()
        prompt_text = "\n".join(str(call.args[0]) for call in prompt.call_args_list)
        self.assertEqual(exit_code, onboarding.GUIDED_DECLINED_EXIT_CODE)
        for name in ("minimal", "balanced", "active"):
            self.assertIn(f"- {name}:", rendered)
        for name in ("off", "advisory", "proposals"):
            self.assertIn(f"- {name}:", rendered)
        self.assertIn("does not create personal values", rendered)
        self.assertIn("Stop proposals stay review-first", rendered)
        self.assertNotIn("Reviewer name", prompt_text)
        self.assertNotIn("Values (required", prompt_text)

    def test_guided_wizard_can_remember_the_applied_vault_as_local_default(self) -> None:
        prompted_answers = ["", "", "yes", "yes"]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            saved = VaultBinding(root.resolve(), "default")
            output = io.StringIO()
            with patch.object(onboarding.sys, "stdin", InteractiveStdin()), patch(
                "builtins.input", side_effect=prompted_answers
            ), patch(
                "ai_dememory_tool.vault_binding.save_default_vault",
                return_value=saved,
            ) as save_default, redirect_stdout(output):
                exit_code = operational_main(["--root", tmp])

            config_exists = (root / ".ai-dememory.toml").exists()

        self.assertEqual(exit_code, 0)
        self.assertTrue(config_exists)
        # The runtime resolver normalizes aliases such as macOS /var and the
        # Windows short temp path before selecting the vault.
        save_default.assert_called_once_with(root.resolve())
        self.assertIn("stores only its absolute path", output.getvalue())
        self.assertIn("Local default vault recorded", output.getvalue())

    def test_default_vault_failure_does_not_undo_successful_operational_setup(self) -> None:
        prompted_answers = ["", "", "yes", "yes"]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = io.StringIO()
            with patch.object(onboarding.sys, "stdin", InteractiveStdin()), patch(
                "builtins.input", side_effect=prompted_answers
            ), patch(
                "ai_dememory_tool.vault_binding.save_default_vault",
                side_effect=VaultBindingError("selector is unavailable"),
            ), redirect_stdout(output):
                exit_code = operational_main(["--root", tmp])

            config = (root / ".ai-dememory.toml").read_text(encoding="utf-8")

        self.assertEqual(exit_code, 0)
        self.assertIn('intensity = "balanced"', config)
        self.assertIn("Could not record the local default", output.getvalue())
        self.assertIn("Setup remains complete", output.getvalue())

    def test_operational_dry_run_does_not_offer_a_default_vault(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = io.StringIO()
            with patch("builtins.input", side_effect=AssertionError("must not prompt")), redirect_stdout(output):
                exit_code = operational_main(["--root", tmp, "--dry-run"])

        self.assertEqual(exit_code, 0)
        self.assertIn("Preview:", output.getvalue())
        self.assertNotIn("local default", output.getvalue())

    def test_guided_next_actions_show_one_valid_mcp_client_example(self) -> None:
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp, redirect_stdout(output):
            onboarding.print_guided_next_actions(
                {
                    "root": str(Path(tmp).resolve()),
                    "clients": ["codex", "claude", "generic"],
                    "setup_scope": "operational",
                }
            )

        rendered = output.getvalue()
        root = str(Path(tmp).resolve())
        codex_command = render_copy_command(
            [
                "ai-dememory",
                "--root",
                root,
                "mcp-config",
                "--client",
                "codex",
            ]
        )
        self.assertIn("setup is complete", rendered)
        self.assertIn("Optional MCP: if you explicitly choose one client", rendered)
        self.assertIn("shown for Codex; replace `codex` with `claude` or `generic`", rendered)
        self.assertIn(codex_command, rendered)
        for client in ("claude", "generic"):
            self.assertNotIn(
                render_copy_command(
                    [
                        "ai-dememory",
                        "--root",
                        root,
                        "mcp-config",
                        "--client",
                        client,
                    ]
                ),
                rendered,
            )

    def test_setup_plan_next_actions_are_conditional(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            ambient_root = Path(tmp) / "ambient"
            root.mkdir()
            ambient_root.mkdir()
            previous_cwd = Path.cwd()
            try:
                os.chdir(ambient_root)
                with patch.dict(
                    os.environ,
                    {"AI_DEMEMORY_ROOT": str(ambient_root)},
                    clear=False,
                ):
                    plan = setup_plan(root)
                    operational = operational_setup_plan(root, operational_answers())
                    onboard_command = render_copy_command(
                        ["ai-dememory", "--root", str(root.resolve()), "onboard"]
                    )
            finally:
                os.chdir(previous_cwd)

        next_actions = plan["next_actions"]
        integration_actions = operational["integrations"]["next_actions"]

        self.assertTrue(
            any(
                action.startswith("After a successful setup, no further command is required;")
                for action in next_actions
            )
        )
        self.assertIn(
            "Optional search: rebuild the index only after you add or review Markdown that you want searchable.",
            next_actions,
        )
        self.assertIn(
            "Optional MCP: choose one client first, then copy only that generated config.",
            next_actions,
        )
        self.assertTrue(any(onboard_command in action for action in next_actions))
        self.assertTrue(
            all(
                action.startswith("Optional ")
                or action.startswith("After a successful setup")
                for action in next_actions
            )
        )
        self.assertTrue(all(action.startswith("Optional ") for action in integration_actions))

    def test_guided_next_actions_offer_a_foreground_loopback_api_without_starting_it(self) -> None:
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp, redirect_stdout(output):
            root = str(Path(tmp).resolve())
            onboarding.print_guided_next_actions(
                {
                    "root": root,
                    "clients": [],
                    "setup_scope": "operational",
                }
            )

        rendered = output.getvalue()
        command = render_copy_command(
            [
                "ai-dememory",
                "--root",
                root,
                "api",
            ]
        )
        self.assertIn(
            "Optional local API for dashboards/scripts, only if you want it "
            "(foreground, loopback-only by default; not started automatically; Ctrl-C stops it):",
            rendered,
        )
        self.assertIn(command, rendered)
        self.assertNotIn("--host", rendered)
        self.assertNotIn("--port", rendered)
        self.assertNotIn("python3 scripts/ai_dememory.py api", rendered)

    def test_copy_command_renderer_quotes_shell_metacharacters(self) -> None:
        argv = [
            "ai-dememory",
            "--root",
            "C:\\vault$(Write-Output PWNED);`x",
            "mcp-config",
            "it's-safe",
        ]
        self.assertEqual(
            render_copy_command(argv, windows=True),
            "& 'ai-dememory' '--root' 'C:\\vault$(Write-Output PWNED);`x' "
            "'mcp-config' 'it''s-safe'",
        )
        import shlex

        self.assertEqual(shlex.split(render_copy_command(argv, windows=False)), argv)

    def test_copy_command_renderer_escapes_powershell_smart_quotes(self) -> None:
        for delimiter in ("\u2018", "\u2019", "\u201a", "\u201b"):
            argv = ["ai-dememory", "--root", f"C:\\vault{delimiter}; Write-Output PWNED"]
            with self.subTest(delimiter=delimiter):
                rendered = render_copy_command(argv, windows=True)
                self.assertEqual(
                    rendered,
                    "& 'ai-dememory' '--root' "
                    f"'C:\\vault{delimiter * 2}; Write-Output PWNED'",
                )

                import shlex

                self.assertEqual(shlex.split(render_copy_command(argv, windows=False)), argv)

    def test_guided_wizard_decline_writes_nothing_and_is_incomplete(self) -> None:
        prompted_answers = [
            "minimal",
            "off",
            "no",
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = io.StringIO()
            with patch.object(onboarding.sys, "stdin", InteractiveStdin()), patch(
                "builtins.input", side_effect=prompted_answers
            ), redirect_stdout(output):
                exit_code = operational_main(["--root", tmp])

            self.assertFalse((root / "memories").exists())
            self.assertFalse((root / ".ai-dememory.toml").exists())

        self.assertEqual(exit_code, onboarding.GUIDED_DECLINED_EXIT_CODE)
        self.assertIn("Setup was not applied", output.getvalue())
        self.assertNotIn("Applied:", output.getvalue())

    def test_guided_json_input_remains_passive_and_noninteractive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = io.StringIO()
            with patch("builtins.input", side_effect=AssertionError("must not prompt")), redirect_stdout(output):
                exit_code = operational_main(
                    [
                        "--root",
                        tmp,
                        "--input-json",
                        json.dumps(operational_answers()),
                        "--json",
                    ]
                )
            payload = json.loads(output.getvalue())

            self.assertFalse((root / "memories").exists())
            self.assertFalse((root / ".ai-dememory.toml").exists())

        self.assertEqual(exit_code, 0)
        self.assertFalse(payload["applied"])
        self.assertTrue(payload["can_apply"])
        self.assertEqual(payload["setup_scope"], "operational")
        self.assertEqual([item["path"] for item in payload["writes"]], [".ai-dememory.toml"])

    def test_guided_input_file_without_json_is_a_passive_preview(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "setup.json"
            input_path.write_text(json.dumps(operational_answers()), encoding="utf-8")
            output = io.StringIO()
            with patch("builtins.input", side_effect=AssertionError("must not prompt")), redirect_stdout(output):
                exit_code = operational_main(["--root", tmp, "--input-file", str(input_path)])

            self.assertFalse((Path(tmp) / ".ai-dememory.toml").exists())

        self.assertEqual(exit_code, 0)
        self.assertIn("Preview:", output.getvalue())
        self.assertIn("plan_sha256:", output.getvalue())

    def test_guided_stdin_without_json_is_a_passive_preview(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = io.StringIO()
            stream = io.StringIO(json.dumps(operational_answers()))
            with patch.object(onboarding.sys, "stdin", stream), patch(
                "builtins.input", side_effect=AssertionError("must not prompt")
            ), redirect_stdout(output):
                exit_code = operational_main(["--root", tmp, "--stdin"])

        self.assertEqual(exit_code, 0)
        self.assertIn("Preview:", output.getvalue())

    def test_setup_rejects_personal_cli_flags_instead_of_ignoring_them(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = operational_main(
                    ["--root", tmp, "--reviewed-by", "Reviewer", "--json"]
                )
            payload = json.loads(output.getvalue())

        self.assertEqual(exit_code, 1)
        self.assertIn("does not accept personal baseline flags", payload["error"])

    def test_onboard_rejects_operational_cli_flags(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = onboarding_main(
                    [
                        "--root", tmp, "--reviewed-by", "Reviewer", "--value", "Safe work",
                        "--preference", "Narrow tests", "--recommendation", "Recall first",
                        "--intensity", "minimal", "--json",
                    ]
                )
            payload = json.loads(output.getvalue())

        self.assertEqual(exit_code, 1)
        self.assertIn("durable baseline fields only", payload["error"])

    def test_guided_json_without_answers_previews_safe_operational_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = io.StringIO()
            with patch.object(onboarding.sys, "stdin", InteractiveStdin()), patch(
                "builtins.input", side_effect=AssertionError("must not prompt")
            ), redirect_stdout(output):
                exit_code = operational_main(["--root", tmp, "--json"])
            payload = json.loads(output.getvalue())

            self.assertFalse((root / ".ai-dememory.toml").exists())
            self.assertFalse((root / "memories").exists())

        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["ok"])
        self.assertFalse(payload["applied"])
        self.assertEqual(payload["setup_scope"], "operational")
        self.assertEqual(payload["automation"]["intensity"], "balanced")
        self.assertEqual(payload["automation"]["model_policy"], "off")

    def test_guided_json_apply_requires_exact_operational_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            preview_output = io.StringIO()
            with redirect_stdout(preview_output):
                preview_exit = operational_main(["--root", tmp, "--json"])
            preview = json.loads(preview_output.getvalue())

            drift_output = io.StringIO()
            with redirect_stdout(drift_output):
                drift_exit = operational_main(
                    [
                        "--root", tmp, "--intensity", "minimal", "--apply",
                        "--expect-plan-sha256", preview["plan_sha256"], "--json",
                    ]
                )

            apply_output = io.StringIO()
            with redirect_stdout(apply_output):
                apply_exit = operational_main(
                    [
                        "--root", tmp, "--apply", "--expect-plan-sha256",
                        preview["plan_sha256"], "--json",
                    ]
                )
            applied = json.loads(apply_output.getvalue())

            self.assertTrue((root / ".ai-dememory.toml").exists())
            self.assertFalse((root / "memories").exists())

        self.assertEqual(preview_exit, 0)
        self.assertEqual(drift_exit, 1)
        self.assertIn("changed after preview", json.loads(drift_output.getvalue())["error"])
        self.assertEqual(apply_exit, 0)
        self.assertTrue(applied["applied"])
        self.assertEqual(applied["changed"], [".ai-dememory.toml"])
        self.assertFalse(applied["installs_hooks"])
        self.assertFalse(applied["installs_schedules"])

    def test_setup_wizard_generated_json_command_executes_without_prompting(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = io.StringIO()
            with patch("builtins.input", side_effect=AssertionError("must not prompt")), redirect_stdout(output):
                exit_code = unified_cli.main(
                    [
                        "--root",
                        tmp,
                        "setup",
                        "wizard",
                        "--json",
                    ]
                )
            payload = json.loads(output.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["setup_scope"], "operational")

    def test_setup_wizard_accepts_legacy_version_arguments_after_an_upgrade(self) -> None:
        output = io.StringIO()
        error = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp:
            with patch("sys.stdout", output), patch("sys.stderr", error):
                exit_code = unified_cli.main(
                    [
                        "--root",
                        tmp,
                        "setup",
                        "wizard",
                        "--require-version",
                        "0.0.0",
                        "--json",
                    ]
                )

        self.assertEqual(exit_code, 0)
        self.assertTrue(json.loads(output.getvalue())["ok"])
        self.assertEqual(error.getvalue(), "")

    def test_guided_json_rejects_personal_baseline_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = io.StringIO()
            with patch("builtins.input", side_effect=AssertionError("must not prompt")), redirect_stdout(output):
                exit_code = operational_main(
                    ["--root", tmp, "--input-json", json.dumps(answers()), "--json"]
                )
            payload = json.loads(output.getvalue())

        self.assertEqual(exit_code, 1)
        self.assertFalse(payload["ok"])
        self.assertIn("use ai-dememory onboard", payload["error"])

    def test_setup_wizard_alias_enables_guided_mode(self) -> None:
        with patch("ai_dememory_tool.cli.run_packaged_command", return_value=0) as runner:
            exit_code = unified_cli.main(["setup", "wizard", "--json"])

        self.assertEqual(exit_code, 0)
        runner.assert_called_once_with(
            "onboard",
            ["--json"],
            onboarding_mode="operational",
        )

    def test_setup_wizard_alias_preserves_a_post_command_root(self) -> None:
        for root_arguments in (["--root", "C:/vault"], ["--root=C:/vault"]):
            with self.subTest(root_arguments=root_arguments):
                with patch("ai_dememory_tool.cli.run_packaged_command", return_value=0) as runner:
                    exit_code = unified_cli.main(["setup", *root_arguments, "wizard", "--json"])

                self.assertEqual(exit_code, 0)
                runner.assert_called_once_with(
                    "onboard",
                    [*root_arguments, "--json"],
                    onboarding_mode="operational",
                )

    def test_direct_onboard_cannot_select_internal_operational_mode(self) -> None:
        with self.assertRaises(SystemExit):
            onboarding_main(["--guided", "--json"])

    def test_command_help_exposes_only_the_selected_scope(self) -> None:
        setup_help = io.StringIO()
        with self.assertRaises(SystemExit), redirect_stdout(setup_help):
            onboarding_main(["--help"], mode="operational")
        onboard_help = io.StringIO()
        with self.assertRaises(SystemExit), redirect_stdout(onboard_help):
            onboarding_main(["--help"])

        self.assertIn("--intensity", setup_help.getvalue())
        self.assertNotIn("--reviewed-by", setup_help.getvalue())
        self.assertIn("--reviewed-by", onboard_help.getvalue())
        self.assertNotIn("--intensity", onboard_help.getvalue())

    def test_init_wizard_propagates_incomplete_guided_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "vault"
            output = io.StringIO()
            with patch(
                "ai_dememory_tool.cli.run_packaged_command",
                return_value=onboarding.GUIDED_DECLINED_EXIT_CODE,
            ) as runner, redirect_stdout(output):
                exit_code = unified_cli.init_vault(
                    [str(target), "--wizard"]
                )

        self.assertEqual(exit_code, onboarding.GUIDED_DECLINED_EXIT_CODE)
        runner.assert_called_once_with(
            "onboard",
            ["--root", str(target.resolve())],
            onboarding_mode="operational",
        )
        self.assertNotIn("Then run `ai-dememory doctor`", output.getvalue())

    def test_init_wizard_completes_operational_setup_without_personal_memory(self) -> None:
        prompted_answers = [
            "balanced",
            "off",
            "yes",
            "no",
        ]
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "vault"
            output = io.StringIO()
            with patch.dict(os.environ, {}, clear=False), patch.object(
                onboarding.sys, "stdin", InteractiveStdin()
            ), patch("builtins.input", side_effect=prompted_answers), redirect_stdout(output):
                exit_code = unified_cli.init_vault(
                    [str(target), "--wizard"]
                )

            config = (target / ".ai-dememory.toml").read_text(encoding="utf-8")
            personal_memory_exists = (target / "memories/durable/onboarding-values.md").exists()

        self.assertEqual(exit_code, 0)
        self.assertIn("Initialized ai-dememory vault", output.getvalue())
        self.assertIn("Preview:", output.getvalue())
        self.assertIn("Applied:", output.getvalue())
        self.assertIn(
            "Optional next actions (setup is complete; nothing else was installed automatically):",
            output.getvalue(),
        )
        self.assertIn('intensity = "balanced"', config)
        self.assertFalse(personal_memory_exists)

    def test_init_wizard_accepts_legacy_version_arguments_after_an_upgrade(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "vault"
            expected_root = str(target.resolve())
            with patch(
                "ai_dememory_tool.cli.run_packaged_command",
                return_value=onboarding.GUIDED_DECLINED_EXIT_CODE,
            ) as runner:
                exit_code = unified_cli.init_vault(
                    [str(target), "--wizard", "--require-version", "0.0.0"]
                )
            target_created = target.exists()

        self.assertEqual(exit_code, onboarding.GUIDED_DECLINED_EXIT_CODE)
        self.assertTrue(target_created)
        runner.assert_called_once_with(
            "onboard",
            ["--root", expected_root],
            onboarding_mode="operational",
        )

        for argv in (
            ["--wiz", "--require-version", PACKAGE_VERSION],
            [
                "--wizard",
                "--require-version",
                PACKAGE_VERSION,
                "--require-version",
                PACKAGE_VERSION,
            ],
        ):
            with self.subTest(argv=argv), tempfile.TemporaryDirectory() as tmp:
                target = Path(tmp) / "vault"
                with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
                    unified_cli.init_vault([str(target), *argv])
                self.assertEqual(raised.exception.code, 2)
                self.assertFalse(target.exists())

    def test_init_without_wizard_binds_its_setup_hint_to_the_new_vault(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            created_vault = Path(tmp) / "created vault"
            ambient_vault = Path(tmp) / "different ambient vault"
            ambient_vault.mkdir()
            output = io.StringIO()
            previous_cwd = Path.cwd()
            try:
                os.chdir(ambient_vault)
                with patch.dict(
                    os.environ,
                    {"AI_DEMEMORY_ROOT": str(ambient_vault)},
                    clear=False,
                ), redirect_stdout(output):
                    exit_code = unified_cli.main(
                        ["init", str(created_vault), "--no-wizard"]
                    )
            finally:
                os.chdir(previous_cwd)

            expected_commands = [
                [
                    "ai-dememory",
                    "--root",
                    str(created_vault.resolve()),
                    "setup",
                    "wizard",
                ],
                [
                    "ai-dememory",
                    "--root",
                    str(created_vault.resolve()),
                    "doctor",
                ],
                [
                    "ai-dememory",
                    "--root",
                    str(created_vault.resolve()),
                    "setup",
                    "health",
                    "--json",
                ],
                [
                    "ai-dememory",
                    "--root",
                    str(created_vault.resolve()),
                    "index",
                ],
            ]
            ambient_entries = list(ambient_vault.iterdir())

        rendered = output.getvalue()

        self.assertEqual(exit_code, 0)
        self.assertIn("Vault creation is complete; no further command is required.", rendered)
        self.assertIn("Optional diagnostics (not setup steps):", rendered)
        self.assertIn(
            "Optional search: after you add or review Markdown that you want searchable,",
            rendered,
        )
        for command in expected_commands:
            self.assertIn(render_copy_command(command), rendered)
        self.assertNotIn("`ai-dememory setup wizard`", rendered)
        self.assertNotIn("`ai-dememory doctor`", rendered)
        self.assertNotIn("`ai-dememory index`", rendered)
        self.assertEqual(ambient_entries, [])

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
            plan = operational_setup_plan(root, operational_answers())
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
                apply_operational_setup(root, operational_answers(), str(plan["plan_sha256"]))

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
            plan = operational_setup_plan(root, operational_answers())
            config_write = next(
                item for item in plan["writes"] if item["path"] == ".ai-dememory.toml"
            )

            result = apply_operational_setup(root, operational_answers(), str(plan["plan_sha256"]))
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
