from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from resource_policy import (  # noqa: E402
    get_model_policy,
    get_resource_profile,
    resolved_resource_policy,
)
from schedule_memory import schedule_plan  # noqa: E402
from setup_plan import setup_health  # noqa: E402


INTENSITY_CANARY = "unexpected-intensity-value-must-not-escape"
MODEL_POLICY_CANARY = "unexpected-model-policy-value-must-not-escape"


class ResourcePolicyRedactionTests(unittest.TestCase):
    def _unexpected_policy_vault(self, temporary: str) -> Path:
        root = Path(temporary) / "vault"
        root.mkdir()
        (root / ".ai-dememory.toml").write_text(
            "\n".join(
                (
                    "[automation]",
                    f'intensity = "{INTENSITY_CANARY}"',
                    f'model_policy = "{MODEL_POLICY_CANARY}"',
                    "",
                )
            ),
            encoding="utf-8",
        )
        return root

    def assert_canaries_redacted(self, value: object) -> None:
        rendered = json.dumps(value, sort_keys=True, default=str)
        self.assertNotIn(INTENSITY_CANARY, rendered)
        self.assertNotIn(MODEL_POLICY_CANARY, rendered)

    def test_direct_enum_diagnostics_do_not_echo_supplied_values(self) -> None:
        cases = (
            (get_resource_profile, INTENSITY_CANARY, "unknown intensity"),
            (get_model_policy, MODEL_POLICY_CANARY, "unknown model policy"),
        )
        for resolver, canary, expected in cases:
            with self.subTest(resolver=resolver.__name__):
                with self.assertRaises(ValueError) as raised:
                    resolver(canary)

                self.assertEqual(str(raised.exception), expected)
                self.assertNotIn(canary, str(raised.exception))
                self.assertIsNone(raised.exception.__cause__)

    def test_resolved_policy_redacts_valid_toml_values_and_falls_back(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._unexpected_policy_vault(temporary)
            policy = resolved_resource_policy(root)

        self.assertFalse(policy["valid"])
        self.assertEqual(policy["intensity"], "balanced")
        self.assertEqual(policy["model_policy"], "off")
        self.assertEqual(
            policy["validation_errors"],
            [
                "invalid_automation_setting:intensity",
                "invalid_automation_setting:model_policy",
            ],
        )
        self.assert_canaries_redacted(policy)

    def test_schedule_plan_does_not_propagate_unexpected_config_values(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._unexpected_policy_vault(temporary)
            plan = schedule_plan(root, target_platform="windows")

        self.assertFalse(plan["resource_policy_valid"])
        self.assertFalse(plan["installable"])
        self.assertEqual(plan["intensity"], "balanced")
        self.assertEqual(
            plan["validation_errors"],
            [
                "invalid_automation_setting:intensity",
                "invalid_automation_setting:model_policy",
            ],
        )
        self.assertEqual(plan["commands"], [])
        self.assertEqual(plan["cron_entries"], [])
        self.assert_canaries_redacted(plan)

    def test_setup_health_does_not_propagate_unexpected_config_values(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._unexpected_policy_vault(temporary)
            health = setup_health(root, target_platform="linux", mode="installed")

        policy = health["resource_policy"]
        self.assertFalse(policy["valid"])
        self.assertFalse(health["core_ready"])
        self.assertEqual(policy["intensity"], "balanced")
        self.assertEqual(policy["model_policy"], "off")
        self.assert_canaries_redacted(health)


if __name__ == "__main__":
    unittest.main()
