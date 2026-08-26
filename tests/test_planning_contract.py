from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
PLANNING = ROOT / "contracts" / "planning"
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from planning_contract import (  # noqa: E402
    validate_json_schema,
    validate_planning_contract,
    validate_sequence_semantics,
)


class PlanningContractTests(unittest.TestCase):
    def test_normative_contract_passes_schema_and_semantic_validation(self) -> None:
        self.assertEqual(validate_planning_contract(ROOT), [])

    def test_execution_sequence_has_one_consistent_public_frontier(self) -> None:
        sequence = json.loads(
            (PLANNING / "v3-execution-sequence.json").read_text(encoding="utf-8")
        )
        tasks = {item["id"]: item for item in sequence["tasks"]}
        batches = {item["id"]: item for item in sequence["batches"]}

        self.assertEqual(len(tasks), len(sequence["tasks"]))
        self.assertEqual(len(batches), len(sequence["batches"]))
        for task in tasks.values():
            self.assertIn(task["batch"], batches)
            self.assertIn(task["id"], batches[task["batch"]]["tasks"])
            self.assertTrue(set(task["depends_on"]).issubset(tasks))
        for batch in batches.values():
            self.assertTrue(set(batch["depends_on"]).issubset(batches))
            self.assertTrue(set(batch["tasks"]).issubset(tasks))

        frontier = sequence["current_frontier"]
        self.assertEqual(frontier, ["BRG-003"])
        self.assertTrue(all(tasks[item]["status"] == "in_progress" for item in frontier))
        self.assertEqual(tasks["BRG-017"]["status"], "complete")
        self.assertTrue(tasks["BRG-017"]["evidence"])
        self.assertEqual(batches["B04c"]["depends_on"], ["B04b"])
        self.assertEqual(tasks["BRG-019"]["batch"], "B04c")
        self.assertEqual(tasks["BRG-019"]["depends_on"], ["BRG-003", "BRG-017"])
        self.assertTrue(tasks["GATE-B"]["external_readback_required"])
        self.assertEqual(batches["B07a"]["depends_on"], ["B06"])
        self.assertEqual(batches["B07a"]["tasks"], ["OBS-001"])
        self.assertEqual(batches["B07b"]["depends_on"], ["B07a"])
        self.assertEqual(batches["B07b"]["tasks"], ["OUT-001"])
        self.assertEqual(batches["B08a"]["depends_on"], ["B07b"])
        self.assertEqual(batches["B08a"]["tasks"], ["CON-001"])
        self.assertEqual(batches["B08b"]["depends_on"], ["B08a"])
        self.assertEqual(batches["B08b"]["tasks"], ["MEM-001"])
        self.assertEqual(tasks["OBS-001"]["batch"], "B07a")
        self.assertEqual(tasks["OBS-001"]["depends_on"], ["GATE-B"])
        self.assertEqual(tasks["OUT-001"]["batch"], "B07b")
        self.assertEqual(tasks["OUT-001"]["depends_on"], ["OBS-001"])
        self.assertEqual(tasks["CON-001"]["batch"], "B08a")
        self.assertEqual(tasks["CON-001"]["depends_on"], ["OUT-001"])
        self.assertEqual(tasks["MEM-001"]["batch"], "B08b")
        self.assertEqual(tasks["MEM-001"]["depends_on"], ["CON-001"])
        self.assertTrue(
            all(
                tasks[item]["status"] == "future" and tasks[item]["evidence"] == []
                for item in ("OBS-001", "OUT-001", "CON-001", "MEM-001")
            )
        )
        self.assertEqual(
            {
                item: tasks[item]["external_readback_required"]
                for item in ("OBS-001", "OUT-001", "CON-001", "MEM-001")
            },
            {"OBS-001": True, "OUT-001": True, "CON-001": False, "MEM-001": True},
        )
        self.assertEqual(batches["B20"]["depends_on"], ["B06"])
        self.assertEqual(tasks["ONB-001"]["depends_on"], ["GATE-B"])
        self.assertTrue(tasks["ONB-001"]["external_readback_required"])

    def test_public_execution_ledger_starts_empty(self) -> None:
        ledger = json.loads(
            (PLANNING / "v3-execution-ledger.json").read_text(encoding="utf-8")
        )

        self.assertEqual(ledger["entries"], [])

    def test_schema_rejects_unknown_task_fields(self) -> None:
        schema = json.loads(
            (PLANNING / "v3-execution-sequence.schema.json").read_text(encoding="utf-8")
        )
        sequence = json.loads(
            (PLANNING / "v3-execution-sequence.json").read_text(encoding="utf-8")
        )
        sequence["tasks"][0]["unreviewed_override"] = True

        errors = validate_json_schema(sequence, schema)

        self.assertTrue(any("unexpected property 'unreviewed_override'" in error for error in errors))

    def test_semantic_guard_rejects_dependency_cycles(self) -> None:
        sequence = json.loads(
            (PLANNING / "v3-execution-sequence.json").read_text(encoding="utf-8")
        )
        cyclic = deepcopy(sequence)
        tasks = {item["id"]: item for item in cyclic["tasks"]}
        tasks["BRG-014"]["depends_on"] = ["BRG-019"]

        errors = validate_sequence_semantics(cyclic, ROOT)

        self.assertTrue(any("task dependency cycle" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
